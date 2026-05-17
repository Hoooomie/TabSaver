@echo off
title TabSaver

:: Install dependencies
pip install -r "%~dp0app\requirements.txt" -q 2>nul

:: Launch desktop app
python "%~dp0app\main.py"
