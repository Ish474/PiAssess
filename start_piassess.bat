@echo off
title PiAssess - Academic Evaluation Suite
cd /d "%~dp0"

echo ============================================================
echo   PiAssess  -  Pi World School, Forbesganj, Bihar
echo   Academic Evaluation Suite  (Session 2026-27)
echo ============================================================
echo.

:: ------------------------------------------------ Python check
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on this computer.
    echo         Please install Python 3.12 from https://www.python.org/downloads/
    echo         and tick "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: ------------------------------------------------ Virtual env + dependencies
if not exist ".venv\Scripts\python.exe" (
    echo First run detected - setting up PiAssess ^(one time only^)...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r backend\requirements.txt
    echo Setup complete.
    echo.
)

:: ------------------------------------------------ Frontend build (only if needed)
if not exist "frontend\dist\index.html" (
    echo Frontend build not found - building the interface...
    where npm.cmd >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] The interface has not been built yet and npm was not found.
        echo         Install Node.js from https://nodejs.org and run this file again,
        echo         or ask your installer for the pre-built version.
        pause
        exit /b 1
    )
    pushd frontend
    call npm.cmd install --no-audit --no-fund
    call npm.cmd run build
    popd
    echo Interface built.
    echo.
)

echo Starting PiAssess...
echo   Address:   http://localhost:8600
echo   First use: username "admin"  password "admin123"
echo              ^(change the password in Settings - Users^)
echo.
echo Keep this window open while using PiAssess. Close it to stop.
echo.

start "" http://localhost:8600
cd backend
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8600
