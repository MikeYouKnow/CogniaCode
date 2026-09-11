@echo off
cd /d "%~dp0"
python main.py --gui
if errorlevel 1 pause
