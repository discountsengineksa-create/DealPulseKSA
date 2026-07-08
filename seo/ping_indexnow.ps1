# نبضة IndexNow يدوية لأي URL
# الاستخدام:
#   .\ping_indexnow.ps1                                     # (يستخدم /calendar افتراضياً)
#   .\ping_indexnow.ps1 https://www.dealpulseksa.com/stores
#   .\ping_indexnow.ps1 https://www.dealpulseksa.com/blog/some-new-post

param(
    [string]$Url = 'https://www.dealpulseksa.com/calendar'
)

# اقرأ السر من .env في الجذر
$envFile = Join-Path (Split-Path $PSScriptRoot) '.env'
$secret = (Get-Content $envFile | Where-Object { $_ -match '^ADMIN_SHARED_SECRET=' }) -replace '^ADMIN_SHARED_SECRET=', ''

if (-not $secret) {
    Write-Host "❌ ADMIN_SHARED_SECRET غير موجود في .env" -ForegroundColor Red
    exit 1
}

Write-Host "🚀 نبضة IndexNow → $Url" -ForegroundColor Cyan

try {
    $r = Invoke-RestMethod `
        -Uri "https://api.dealpulseksa.com/api/v1/admin/seo-resubmit-url?url=$Url" `
        -Method POST `
        -Headers @{ 'X-Admin-Secret' = $secret }

    Write-Host ""
    Write-Host "النتيجة:" -ForegroundColor Green
    $r | ConvertTo-Json -Depth 5
} catch {
    Write-Host "❌ فشل: $_" -ForegroundColor Red
    exit 1
}
