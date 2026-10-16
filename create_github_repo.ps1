# PowerShell Script to Create & Push AquaVigil to GitHub
# Google Cloud AI Builder Cup 2026

Set-Location -Path $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "AquaVigil: Create & Push to GitHub Repository" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Initialize Git repository
if (-not (Test-Path ".git")) {
    Write-Host "`n[1/4] Initializing local Git repository..." -ForegroundColor Green
    git init
} else {
    Write-Host "`n[1/4] Git repository already initialized." -ForegroundColor Yellow
}

# 2. Stage and Commit files
Write-Host "`n[2/4] Staging files and creating initial commit..." -ForegroundColor Green
git add .
git commit -m "Initial commit: AquaVigil Platform for Google Cloud AI Builder Cup 2026 (Track: Sustainability & Community Resilience)"

git branch -M main

# 3. Check for GitHub CLI (gh)
$hasGh = Get-Command gh -ErrorAction SilentlyContinue

if ($hasGh) {
    Write-Host "`n[3/4] GitHub CLI (gh) detected!" -ForegroundColor Green
    $repoName = Read-Host "Enter desired GitHub repository name [default: aquavigil]"
    if (-not $repoName) { $repoName = "aquavigil" }

    Write-Host "Creating public repository on GitHub..." -ForegroundColor Cyan
    gh repo create $repoName --public --source=. --remote=origin --push
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n[4/4] Successfully created and pushed to GitHub!" -ForegroundColor Green
        Exit 0
    }
}

# 4. Manual Remote Configuration Fallback
Write-Host "`n[3/4] Configure GitHub Remote URL manually:" -ForegroundColor Yellow
Write-Host "Create a new empty repository at https://github.com/new" -ForegroundColor White
$remoteUrl = Read-Host "Paste your GitHub repository URL (e.g. https://github.com/username/aquavigil.git)"

if ($remoteUrl) {
    git remote remove origin -ErrorAction SilentlyContinue
    git remote add origin $remoteUrl
    Write-Host "`n[4/4] Pushing to main branch..." -ForegroundColor Green
    git push -u origin main
    Write-Host "`nDone! Repository is live at: $remoteUrl" -ForegroundColor Cyan
} else {
    Write-Host "`nNo URL provided. Files are committed locally on branch 'main'." -ForegroundColor Yellow
    Write-Host "When ready, link remote with: git remote add origin <URL> && git push -u origin main" -ForegroundColor White
}
