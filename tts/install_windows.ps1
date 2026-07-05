# DealPulse local TTS — Windows bootstrap (Coqui XTTS v2, Arabic-capable)
# Run once from repo root:
#   powershell -ExecutionPolicy Bypass -File tts\install_windows.ps1
#
# Flags:
#   -Gpu      install CUDA 12.1 build of torch (auto-detected if omitted)
#   -SkipTorch   skip torch install (already have it)

param(
    [switch]$Gpu,
    [switch]$SkipTorch
)

$ErrorActionPreference = "Stop"

Write-Host "==> Persisting COQUI_TOS_AGREED=1 (auto-accepts XTTS v2 CPML terms)" -ForegroundColor Cyan
[Environment]::SetEnvironmentVariable("COQUI_TOS_AGREED", "1", "User")
$env:COQUI_TOS_AGREED = "1"

if (-not $SkipTorch) {
    $index = if ($Gpu) { "https://download.pytorch.org/whl/cu121" } else { "https://download.pytorch.org/whl/cpu" }
    Write-Host "==> Installing torch + torchaudio 2.8.x ($(if($Gpu){'CUDA 12.1'}else{'CPU'}) wheel)" -ForegroundColor Cyan
    python -m pip install --upgrade pip
    # torchaudio is a hard dep of coqui-tts (xtts loader imports it at module init).
    # Pin the 2.8 line: torch 2.9+ makes coqui-tts hard-require `torchcodec`
    # (+ system FFmpeg), which has no reliable Windows wheel. See tts\requirements.txt.
    python -m pip install "torch==2.8.*" "torchaudio==2.8.*" --index-url $index
}

Write-Host "==> Installing coqui-tts + FastAPI stack" -ForegroundColor Cyan
python -m pip install -r tts\requirements.txt

Write-Host "==> Warming XTTS v2 (first run downloads ~1.9 GB model)" -ForegroundColor Cyan
# Route through tts.service, NOT `from TTS.api import TTS` directly: the service
# module installs the transformers isin_mps_friendly shim and the NUMBA_CACHE_DIR
# redirect that a raw TTS import would miss (and then crash on).
python -c @"
import os
os.environ['COQUI_TOS_AGREED'] = '1'
from tts.service import get_tts
get_tts()
print('XTTS v2 OK')
"@

Write-Host "`nDone. Start the service with:" -ForegroundColor Green
Write-Host "  python -m uvicorn tts.service:app --host 127.0.0.1 --port 8770"
Write-Host ""
Write-Host "To use a custom voice: drop a 6-30s WAV/MP3 into tts\reference_voices\ and call /tts with voice=<filename-without-extension>." -ForegroundColor Yellow
