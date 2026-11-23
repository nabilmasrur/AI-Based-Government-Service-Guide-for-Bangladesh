@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Seba Sohayok - Live Server

echo ====================================================
echo   Seba Sohayok - AI Government Service Guide for BD
echo   Starting Live Server with Hot-Reload...
echo ====================================================
echo.

python run_live.py

if errorlevel 1 (
    echo.
    echo [!] Server exited or Python is not found.
    pause
)
