@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
  echo [ERROR] Project virtual environment was not found.
  echo Run install_demo.cmd first.
  exit /b 1
)

echo [1/4] Checking Python and Playwright...
"%VENV_PYTHON%" scripts\check_environment.py --renderer-only
if errorlevel 1 exit /b 1

echo [2/4] Applying database migrations...
"%VENV_PYTHON%" -m alembic upgrade head
if errorlevel 1 exit /b 1

echo [3/4] Preparing demo data...
"%VENV_PYTHON%" scripts\seed_demo.py
if errorlevel 1 exit /b 1

echo [4/4] Running full environment check...
"%VENV_PYTHON%" scripts\check_environment.py
if errorlevel 1 exit /b 1

echo.
echo Demo URL: http://127.0.0.1:8030
echo Login: agent / demo1234
echo Press Ctrl+C to stop the server.
echo.
"%VENV_PYTHON%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8030
