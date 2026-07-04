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
    Write-Host "==> Installing torch ($(if($Gpu){'CUDA 12.1'}else{'CPU'}) wheel)" -ForegroundColor Cyan
    python -m pip install --upgrade pip
    python -m pip install torch --index-url $index
}

Write-Host "==> Installing coqui-tts + FastAPI stack" -ForegroundColor Cyan
python -m pip install -r tts\requirements.txt

Write-Host "==> Warming XTTS v2 (first run downloads ~1.9 GB model)" -ForegroundColor Cyan
python -c @"
import os
os.environ['COQUI_TOS_AGREED'] = '1'
from TTS.api import TTS
_ = TTS('tts_models/multilingual/multi-dataset/xtts_v2')
print('XTTS v2 OK')
"@

Write-Host "`nDone. Start the service with:" -ForegroundColor Green
Write-Host "  python -m uvicorn tts.service:app --host 127.0.0.1 --port 8770"
Write-Host ""
Write-Host "To use a custom voice: drop a 6-30s WAV/MP3 into tts\reference_voices\ and call /tts with voice=<filename-without-extension>." -ForegroundColor Yellow
