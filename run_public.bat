@echo off
setlocal
cd /d "%~dp0"
title Seba Sohayok - Public Live Tunnel ^& Server

echo ======================================================================
echo   SEBA SOHAYOK - AI GOVERNMENT SERVICE GUIDE FOR BANGLADESH
echo   Starting Public Live Tunnel ^& Server...
echo ======================================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in your system PATH.
    echo Please install Python 3.10+ from python.org and add it to PATH.
    echo.
    pause
    exit /b 1
)

python run_live.py

if errorlevel 1 (
    echo.
    echo [!] Process exited with code %errorlevel%.
    pause
)
