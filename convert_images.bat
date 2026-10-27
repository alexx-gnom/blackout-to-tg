@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3"
) else (
    set "PY=python"
)
%PY% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3 not found. Install Python 3 from python.org.
    pause
    exit /b 1
)
%PY% -c "from PIL import Image" >nul 2>&1
if errorlevel 1 (
    echo Installing Pillow library...
    %PY% -m pip install Pillow
    if errorlevel 1 (
        echo ERROR: Could not install Pillow.
        pause
        exit /b 1
    )
)
%PY% "%~dp0convert_images.py"
echo.
pause
