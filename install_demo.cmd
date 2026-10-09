@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating project virtual environment...
  python -m venv .venv
  if errorlevel 1 exit /b 1
)

echo Installing Python dependencies into .venv...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Installing Playwright Chromium...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 exit /b 1

echo Installation complete. Run start_demo.cmd.
