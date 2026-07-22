@echo off
cd /d "%~dp0"
set PYTHON=python
"%PYTHON%" -c "import PyQt6" >nul 2>&1
if errorlevel 1 "%PYTHON%" -m pip install PyQt6
"%PYTHON%" run.py
if errorlevel 1 pause
