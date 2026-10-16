Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "AquaVigil: Subterranean Cross-Contamination & Purifier Health Sentry" -ForegroundColor White
Write-Host "Google Cloud AI Builder Cup 2026 - Track: Sustainability & Community Resilience" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

Set-Location -Path $PSScriptRoot

$pythonCmd = $null

if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} else {
    $possiblePaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "C:\Program Files\Python3*\python.exe",
        "C:\Python3*\python.exe"
    )
    foreach ($pattern in $possiblePaths) {
        $resolved = Resolve-Path $pattern -ErrorAction SilentlyContinue
        if ($resolved) {
            $pythonCmd = $resolved[0].Path
            break
        }
    }
}

if (-not $pythonCmd) {
    Write-Host "`n[ERROR] Python is not found on your system PATH." -ForegroundColor Red
    Exit 1
}

Write-Host "`nLaunching AquaVigil on http://127.0.0.1:8080 ..." -ForegroundColor Green
Write-Host "Open your browser at: http://127.0.0.1:8080" -ForegroundColor Yellow
& $pythonCmd main.py
