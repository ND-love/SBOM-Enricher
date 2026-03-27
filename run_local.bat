@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo ==========================================
echo   Cert Checker - local startup
echo ==========================================
echo.

REM 1. Create venv if missing
if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating virtual environment...
    py -3.11 -m venv .venv 2>nul
    if errorlevel 1 (
        python -m venv .venv
        if errorlevel 1 (
            echo ERROR: Failed to create virtual environment.
            echo Install Python 3.11+ and make sure it is available in PATH.
            pause
            exit /b 1
        )
    )
) else (
    echo [1/5] Virtual environment already exists.
)

echo.
echo [2/5] Installing/updating dependencies...
.\.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: pip upgrade failed.
    pause
    exit /b 1
)

.\.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 (
    echo ERROR: dependency installation failed.
    pause
    exit /b 1
)

echo.
echo [3/5] Importing Astra catalog into SQLite...
if exist "data\raw\astra\*.txt" (
    .\.venv\Scripts\python.exe .\scripts\import_astra.py
    if errorlevel 1 (
        echo ERROR: Astra import failed.
        pause
        exit /b 1
    )
) else (
    echo WARNING: No Astra txt files found in data\raw\astra
    echo The site will start, but checks may not work until catalog files are added.
)

echo.
echo [4/5] Starting local web server...
start "Cert Checker UI" cmd /k ".\.venv\Scripts\python.exe -m uvicorn app.main:app --reload"

echo.
echo [5/5] Opening browser...
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000"

echo.
echo Done.
echo Browser should open automatically.
echo To stop the server, close the "Cert Checker UI" console window.
echo.
exit /b 0