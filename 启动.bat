@echo off
cd /d "%~dp0"
set PYTHON=python
"%PYTHON%" -c "import PyQt6; import PyQt6.QtWebEngineWidgets; import PyQt6.QtWebChannel" >nul 2>&1
if errorlevel 1 (
    "%PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install required Python packages.
        pause
        exit /b 1
    )
)
"%PYTHON%" run.py
if errorlevel 1 pause
