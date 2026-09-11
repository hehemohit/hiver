@echo off
setlocal
title @AppleSupport AI Agent - Recruiter Quick Launch

echo ========================================================================
echo         @AppleSupport AI Support Agent — Quick Launch
echo ========================================================================
echo.

cd /d "%~dp0"

REM 1. Activate virtual environment if available
if exist "venv\Scripts\activate.bat" (
    echo [*] Activating local virtual environment (venv)...
    call "venv\Scripts\activate.bat"
) else (
    echo [!] No venv folder detected; using system Python.
)

REM 2. Verify Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 3. Run the interactive demonstration
echo [*] Starting demonstration...
python demo.py

echo.
pause
