@echo off
REM Setup launcher for the GA4 + GSC Data Exporter (Windows).
REM Double-click this file (or run from a terminal) to create a venv,
REM install dependencies, and install the Chromium browser used by Playwright.

setlocal
cd /d "%~dp0"

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Activating venv and installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Installing Chromium for Playwright (one-time download)...
python -m playwright install chromium

echo.
echo Setup complete. Launch the app with:  run.bat
echo.
pause
endlocal
