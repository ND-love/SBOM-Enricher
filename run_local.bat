@echo off
setlocal
pushd "%~dp0" || exit /b 1

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>&1
    if errorlevel 1 (
        python -m venv .venv || goto :python_error
    ) else (
        py -3 -m venv .venv || goto :python_error
    )
)

set "PYTHON=.venv\Scripts\python.exe"
"%PYTHON%" -c "import sys; sys.exit(sys.version_info < (3, 11))" || goto :python_error
"%PYTHON%" -m pip install -e . || goto :failed
"%PYTHON%" -m scripts.import_astra || goto :failed

if not defined CERT_CHECKER_PORT set "CERT_CHECKER_PORT=8000"
echo Open http://127.0.0.1:%CERT_CHECKER_PORT%/sbom in your browser. Press Ctrl+C to stop.
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port "%CERT_CHECKER_PORT%" || goto :failed
popd
exit /b 0

:python_error
echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
echo If an older virtual environment exists, recreate .venv with the new Python.
:failed
popd
pause
exit /b 1
