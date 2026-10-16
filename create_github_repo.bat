@echo off
title Create GitHub Repository - AquaVigil Platform
echo ========================================================
echo AquaVigil: Create and Push to GitHub Repository
echo Google Cloud AI Builder Cup 2026
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Initializing local git repository and committing...
git init
git add .
git commit -m "Initial commit: AquaVigil Platform for Google Cloud AI Builder Cup 2026"
git branch -M main

where gh >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [2/3] GitHub CLI detected. Creating repository on GitHub...
    gh repo create aquavigil --public --source=. --remote=origin --push
    if %ERRORLEVEL% EQU 0 (
        echo [3/3] Successfully pushed to GitHub!
        pause
        exit /b 0
    )
)

echo.
echo [2/3] Please create a new empty repository at https://github.com/new
set /p REPO_URL="Enter your GitHub Repository URL (e.g., https://github.com/username/aquavigil.git): "

if not "%REPO_URL%"=="" (
    git remote remove origin >nul 2>&1
    git remote add origin %REPO_URL%
    echo.
    echo [3/3] Pushing to GitHub...
    git push -u origin main
    echo.
    echo Done! Your code is now live on GitHub.
) else (
    echo.
    echo All files are committed locally to main branch.
    echo You can push later using:
    echo   git remote add origin ^<YOUR_GITHUB_URL^>
    echo   git push -u origin main
)

pause
