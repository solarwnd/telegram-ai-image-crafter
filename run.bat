@echo off
title Telegram ComfyUI Bot

echo ===========================================
echo Starting Telegram Bot with CV and ComfyUI
echo ===========================================

cd /d "%~dp0"

IF NOT EXIST venv (
    echo [INFO] Virtual environment not found. Creating venv...
    python -m venv venv
)

echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

echo [INFO] Installing/updating dependencies (this might take a few minutes)...
pip install -r requirements.txt --quiet

echo [INFO]===========================================
echo [INFO] Starting bot.py...
echo [INFO]===========================================
python bot.py

echo.
echo Bot stopped.
pause
