"""
DealPulse local TTS service — Coqui XTTS v2 backend.

100% local. No API keys. Runs on CPU (~5-8× realtime) or CUDA (~40× realtime).

Why XTTS v2 over Kokoro
-----------------------
Kokoro-82M has no Arabic voice. XTTS v2 speaks Arabic natively AND supports
zero-shot voice cloning from a 6-30s reference clip — which is exactly how you
get the "restrained, professional, not-radio-cheesy" tone the brief asked for.

Voice modes
-----------
1. Built-in studio speaker  →  voice="Damien Black"           (default, no setup)
2. Cloned from reference    →  voice="anchor_male_calm"       (WAV/MP3 in tts/reference_voices/)

Endpoints
---------
POST /tts              — one input → one MP3
POST /tts/batch        — many inputs (amortizes model load)
GET  /download/{name}  — stream a produced MP3
GET  /voices           — curated studio speakers + custom clips discovered on disk
GET  /health           — liveness + device + loaded state

License note
------------
XTTS v2 ships under Coqui Public Model License (non-commercial by default;
commercial use requires a Coqui license — Coqui as a company shut down 2024,
so this is a legal gray zone). If you need pure Apache-2.0 for commercial use,
say the word and I'll swap the engine for Facebook MMS-TTS Arabic.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from threading import Lock

# Auto-accept XTTS v2 CPML terms so headless boot doesn't prompt.
os.environ.setdefault("COQUI_TOS_AGREED", "1")

# librosa's numba-JIT'd DSP kernels default their compile cache into
# site-packages/librosa/__pycache__, which is often read-only or stale and, on
# Windows, can crash llvmlite's module serializer ("LLVMPY_CloneModule ...
# No name entry found", WinError 0xe06d7363). Redirect the cache to a writable,
# persistent, per-user dir so the first compile is cached cleanly and reused.
os.environ.setdefault(
    "NUMBA_CACHE_DIR", str(Path(tempfile.gettempdir()) / "dealpulse_numba_cache")
)
Path(os.environ["NUMBA_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)

import lameenc
import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# ── transformers compat shim ──────────────────────────────────────────
# coqui-tts's tortoise layer hard-imports `isin_mps_friendly` from
# transformers.pytorch_utils. That helper existed only in transformers
# 4.41–4.49 and was dropped in 4.50+, yet coqui-tts 0.27.x still requires
# transformers>=4.57 (which no longer ships it) — an upstream mismatch that
# makes `from TTS.api import TTS` fail on any modern transformers. The helper
# was always just a torch.isin wrapper with an MPS fallback (see the upstream
# "TODO: use torch.isin from Pytorch 2.4" comment), so on torch>=2.4 we can
# provide an equivalent ourselves and stay decoupled from the transformers
# version entirely.
import transformers.pytorch_utils as _tf_pytorch_utils  # noqa: E402

if not hasattr(_tf_pytorch_utils, "isin_mps_friendly"):
    def _isin_mps_friendly(elements: "torch.Tensor", test_elements: "torch.Tensor") -> "torch.Tensor":
        if elements.device.type == "mps":  # pre-2.4 MPS lacked torch.isin
            return (elements.unsqueeze(-1) == test_elements).any(dim=-1)
        return torch.isin(elements, test_elements)

    _tf_pytorch_utils.isin_mps_friendly = _isin_mps_friendly

from TTS.api import TTS  # noqa: E402  (must follow the shim above)

log = logging.getLogger("dealpulse.tts")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# ─── Paths ────────────────────────────────────────────────────────────
TTS_DIR       = Path(__file__).resolve().parent
REF_VOICE_DIR = TTS_DIR / "reference_voices"
OUTPUT_DIR    = Path(os.getenv("TTS_OUTPUT_DIR", "generated_audio")).resolve()
REF_VOICE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Engine config ────────────────────────────────────────────────────
MODEL_ID     = "tts_models/multilingual/multi-dataset/xtts_v2"
SAMPLE_RATE  = 24_000                             # XTTS v2 native rate
MP3_BITRATE  = int(os.getenv("TTS_MP3_BITRATE", "128"))
DEVICE       = "cuda" if torch.cuda.is_available() else "cpu"

DEFAULT_LANG    = "ar"                            # Arabic — the primary use case
DEFAULT_VOICE   = "Damien Black"                  # calm baritone studio speaker
DEFAULT_SPEED   = 1.0
MAX_CHUNK_CHARS = 240                             # XTTS v2 hard limit ~400 tokens

# XTTS v2 supported languages (from model config).
SUPPORTED_LANGS = {"ar", "en", "es", "fr", "de", "it", "pt", "pl", "tr",
                   "ru", "nl", "cs", "zh-cn", "ja", "hu", "ko", "hi"}

# Studio speakers curated for the "professional, restrained" brief.
# Cross-lingual: these actors' timbre is preserved when speaking Arabic.
STUDIO_SPEAKERS: dict[str, list[str]] = {
    "authoritative_male": ["Damien Black", "Viktor Menelaos", "Royston Min"],
    "calm_male":          ["Adde Michal", "Aaron Dreschner", "Filip Traverse"],
    "warm_female":        ["Sofia Hellen", "Ana Florence", "Alison Dietlinde"],
    "measured_female":    ["Brenda Stern", "Rosemary Okafor", "Lidiya Szekeres"],
}
_ALL_STUDIO = {v for group in STUDIO_SPEAKERS.values() for v in group}

# ─── Model bootstrap ──────────────────────────────────────────────────
_tts: TTS | None = None
_tts_lock = Lock()      # XTTS v2 forward pass is not thread-safe


def get_tts() -> TTS:
    global _tts
    if _tts is None:
        with _tts_lock:
            if _tts is None:
                log.info("loading XTTS v2 on device=%s (first call ~2GB download)", DEVICE)
                _tts = TTS(MODEL_ID).to(DEVICE)
    return _tts


# ─── Text handling ────────────────────────────────────────────────────
_SENTENCE_SPLIT_LATIN = re.compile(r"(?<=[\.\!\?…])\s+")
_SENTENCE_SPLIT_AR    = re.compile(r"(?<=[\.\!\?…؟؛])\s+")
_WS = re.compile(r"[ \t]+")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").strip()
    text = _WS.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[`*_#>]+", "", text)                # strip markdown scaffolding
    text = re.sub(r"\s*\n\s*", " ", text)               # linebreaks → spaces for TTS
    return text.strip()


def chunk_text(text: str, lang: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    splitter = _SENTENCE_SPLIT_AR if lang == "ar" else _SENTENCE_SPLIT_LATIN
    sentences = [s for s in splitter.split(text) if s]
    chunks: list[str] = []
    buf = ""
    for s in sentences:
        candidate = f"{buf} {s}".strip() if buf else s
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
        if len(s) > max_chars:
            # sentence itself too long → hard split on word boundaries
            words = s.split(" ")
            piece = ""
            for w in words:
                trial = f"{piece} {w}".strip()
                if len(trial) <= max_chars:
                    piece = trial
                else:
                    if piece:
                        chunks.append(piece)
                    piece = w
            if piece:
                chunks.append(piece)
            buf = ""
        else:
            buf = s
    if buf:
        chunks.append(buf)
    return chunks or [text]


# ─── Voice resolution ─────────────────────────────────────────────────
def _resolve_reference_wav(name: str) -> Path | None:
    """Find a reference clip by stem (WAV preferred, then MP3)."""
    for ext in (".wav", ".mp3", ".flac", ".ogg"):
        p = REF_VOICE_DIR / f"{name}{ext}"
        if p.is_file():
            return p
    return None


def _list_reference_voices() -> list[str]:
    return sorted(
        {p.stem for p in REF_VOICE_DIR.iterdir()
         if p.is_file() and p.suffix.lower() in {".wav", ".mp3", ".flac", ".ogg"}}
    )


def _find_ffmpeg() -> str | None:
    """Locate an ffmpeg binary: PATH first, then the winget install dir."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    # winget (Gyan.FFmpeg) drops the binary here; PATH may not be refreshed yet
    # in an already-running process, so fall back to a glob.
    root = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    hits = glob.glob(os.path.join(root, "Gyan.FFmpeg*", "**", "bin", "ffmpeg.exe"),
                     recursive=True)
    return hits[0] if hits else None


def ffmpeg_available() -> bool:
    return _find_ffmpeg() is not None


def import_reference_clip(data: bytes, orig_name: str, voice_name: str,
                          start: float = 0.0, duration: float = 20.0) -> Path:
    """Extract a clean mono reference clip from an uploaded audio/video file.

    Runs ffmpeg to pull `duration` seconds starting at `start`, downmixed to
    mono at the XTTS sample rate, and stores it as
    reference_voices/<voice_name>.wav so it shows up as a cloneable voice.
    Works for both audio (mp3/wav/m4a/…) and video (mp4/mov/…) inputs.
    """
    ff = _find_ffmpeg()
    if not ff:
        raise RuntimeError(
            "ffmpeg غير متوفّر. ثبّته: winget install --id Gyan.FFmpeg، "
            "ثم أعد تشغيل الداشبورد."
        )
    # sanitize name → keep Arabic letters, word chars, space, dash
    safe = re.sub(r"[^\w؀-ۿ \-]", "", voice_name or "").strip()
    if not safe:
        raise ValueError("اسم الصوت مطلوب.")
    suffix = Path(orig_name).suffix or ".bin"
    tmp = OUTPUT_DIR / f"_upload_{uuid.uuid4().hex}{suffix}"
    tmp.write_bytes(data)
    out = REF_VOICE_DIR / f"{safe}.wav"
    try:
        cmd = [ff, "-y", "-ss", f"{max(0.0, start):.3f}", "-t", f"{max(1.0, duration):.3f}",
               "-i", str(tmp), "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
               "-c:a", "pcm_s16le", str(out)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError(f"ffmpeg فشل: {(res.stderr or '')[-400:]}")
    finally:
        tmp.unlink(missing_ok=True)
    return out


# ─── Synthesis ────────────────────────────────────────────────────────
def synthesize(text: str, voice: str, language: str, speed: float) -> np.ndarray:
    tts = get_tts()
    ref_wav = _resolve_reference_wav(voice)
    parts: list[np.ndarray] = []

    with _tts_lock:
        for chunk in chunk_text(text, language):
            kwargs: dict = {"text": chunk, "language": language, "speed": speed}
            if ref_wav is not None:
                kwargs["speaker_wav"] = str(ref_wav)
            elif voice in _ALL_STUDIO:
                kwargs["speaker"] = voice
            else:
                raise ValueError(
                    f"voice '{voice}' not recognized. Provide a studio speaker "
                    f"(see /voices) or drop a WAV into tts/reference_voices/."
                )
            wav = tts.tts(**kwargs)                     # returns list[float]
            parts.append(np.asarray(wav, dtype=np.float32))

    if not parts:
        raise ValueError("model produced no audio for this input")
    return np.concatenate(parts, axis=0)


def encode_mp3(pcm_f32: np.ndarray, out_path: Path) -> Path:
    pcm_i16 = np.clip(pcm_f32 * 32767.0, -32768, 32767).astype(np.int16)
    enc = lameenc.Encoder()
    enc.set_bit_rate(MP3_BITRATE)
    enc.set_in_sample_rate(SAMPLE_RATE)
    enc.set_channels(1)
    enc.set_quality(2)
    payload = enc.encode(pcm_i16.tobytes())
    payload += enc.flush()
    out_path.write_bytes(payload)
    return out_path


# ─── FastAPI ──────────────────────────────────────────────────────────
app = FastAPI(title="DealPulse Local TTS (XTTS v2)", version="2.0.0")


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000)
    voice: str = Field(DEFAULT_VOICE, description="Studio speaker name OR reference clip stem")
    language: str = Field(DEFAULT_LANG, description="ISO code; see SUPPORTED_LANGS")
    speed: float = Field(DEFAULT_SPEED, ge=0.5, le=2.0)
    filename: str | None = Field(None, description="Output stem; auto-generated if omitted")


class BatchRequest(BaseModel):
    items: list[TTSRequest] = Field(..., min_length=1, max_length=32)


class TTSResult(BaseModel):
    filename: str
    path: str
    duration_sec: float
    voice: str
    language: str


def _safe_stem(name: str | None) -> str:
    if not name:
        return f"tts_{uuid.uuid4().hex[:12]}"
    stem = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_")
    return stem or f"tts_{uuid.uuid4().hex[:12]}"


def _run_one(req: TTSRequest) -> TTSResult:
    if req.language not in SUPPORTED_LANGS:
        raise HTTPException(422, f"language '{req.language}' not supported; see /voices")
    text = normalize_text(req.text)
    if not text:
        raise HTTPException(422, "text is empty after normalization")
    try:
        audio = synthesize(text, req.voice, req.language, req.speed)
    except ValueError as e:
        raise HTTPException(422, str(e))
    out = OUTPUT_DIR / f"{_safe_stem(req.filename)}.mp3"
    encode_mp3(audio, out)
    return TTSResult(
        filename=out.name,
        path=str(out),
        duration_sec=round(len(audio) / SAMPLE_RATE, 3),
        voice=req.voice,
        language=req.language,
    )


@app.on_event("startup")
def _warmup() -> None:
    get_tts()
    log.info(
        "TTS ready. device=%s output_dir=%s default=(%s / %s)",
        DEVICE, OUTPUT_DIR, DEFAULT_VOICE, DEFAULT_LANG,
    )


@app.post("/tts", response_model=TTSResult)
def tts_one(req: TTSRequest) -> TTSResult:
    return _run_one(req)


@app.post("/tts/batch", response_model=list[TTSResult])
def tts_batch(req: BatchRequest) -> list[TTSResult]:
    # Sequential on purpose — XTTS v2 forward pass is not thread-safe,
    # and the value of "batch" here is amortized model load + warm GPU cache.
    return [_run_one(item) for item in req.items]


@app.get("/download/{filename}")
def download(filename: str) -> FileResponse:
    path = (OUTPUT_DIR / filename).resolve()
    if OUTPUT_DIR not in path.parents or not path.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(path, media_type="audio/mpeg", filename=filename)


@app.get("/voices")
def voices() -> dict[str, object]:
    return {
        "studio_speakers": STUDIO_SPEAKERS,
        "reference_clips": _list_reference_voices(),
        "supported_languages": sorted(SUPPORTED_LANGS),
        "default_voice": DEFAULT_VOICE,
        "default_language": DEFAULT_LANG,
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "engine": "coqui-xtts-v2",
        "device": DEVICE,
        "loaded": _tts is not None,
        "output_dir": str(OUTPUT_DIR),
        "reference_voice_dir": str(REF_VOICE_DIR),
    }
