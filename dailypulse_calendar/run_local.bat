@echo off
cd /d "%~dp0\.."
py -3 "dailypulse_calendar\generate_daily.py" --check-images
if errorlevel 1 (
  echo Failed. Check image filenames and Python installation.
)
pause
