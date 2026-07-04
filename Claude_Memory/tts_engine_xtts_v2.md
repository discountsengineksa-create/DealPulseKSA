---
name: Local TTS Engine — XTTS v2
description: Local TTS for DealPulse runs on Coqui XTTS v2 (Arabic + voice cloning), not Kokoro
type: project
originSessionId: ce97ea79-0034-4f51-b8fb-e7e36536ea26
---
Local text-to-speech for DealPulse (بديل ElevenLabs) is built on **Coqui XTTS v2**, exposed via FastAPI at `tts/service.py`, port 8770.

**Why:** Kokoro-82M was the first pick but has zero Arabic support (9 languages: a/b/e/f/h/i/j/p/z — `a` is American English not Arabic; confirmed against `hexgrad/Kokoro-82M/VOICES.md` on 2026-07-04). XTTS v2 speaks Arabic natively and supports zero-shot voice cloning from a 6–30s reference clip — which is how we hit the "professional restrained tone" brief without paying for ElevenLabs.

**How to apply:**
- Any future TTS work → extend `tts/service.py`, don't propose a new engine
- If someone suggests Kokoro/Piper/MMS for Arabic, remind them Kokoro is English-only and XTTS is already installed
- License caveat: XTTS v2 is CPML (non-commercial default). Coqui shut down 2024 so enforcement is nil, but if commercial legality gets flagged, the pre-planned fallback is Facebook MMS-TTS Arabic (Apache-2.0, lower quality)
- Voice modes: (1) built-in studio speaker like `Damien Black`, or (2) drop WAV/MP3 into `tts/reference_voices/` and pass filename stem as `voice`
