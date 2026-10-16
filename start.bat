@echo off
title AquaVigil Platform - Google Cloud AI Builder Cup 2026
echo ========================================================
echo AquaVigil: Subterranean Cross-Contamination & Purifier Health Sentry
echo Google Cloud AI Builder Cup 2026 - Track: Sustainability & Community Resilience
echo ========================================================
echo.

cd /d "%~dp0"

:: 1. Detect Python or Py launcher
set PYTHON_CMD=

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=py
    goto :FOUND_PYTHON
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=python
    goto :FOUND_PYTHON
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_CMD=%%D\python.exe"
        goto :FOUND_PYTHON
    )
)

for /d %%D in ("C:\Program Files\Python3*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_CMD=%%D\python.exe"
        goto :FOUND_PYTHON
    )
)

for /d %%D in ("C:\Python3*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_CMD=%%D\python.exe"
        goto :FOUND_PYTHON
    )
)

echo [ERROR] Python was not found on your system!
echo Please download and install Python from https://www.python.org/downloads/
echo.
pause
exit /b 1

:FOUND_PYTHON
echo Starting AquaVigil Platform on http://127.0.0.1:8080 ...
echo Open your browser at: http://127.0.0.1:8080
echo Press Ctrl+C to stop the server.
echo.

"%PYTHON_CMD%" main.py
pause
