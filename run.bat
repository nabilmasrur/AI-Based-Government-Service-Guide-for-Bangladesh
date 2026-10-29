@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Seba Sohayok - Government Service Assistant

echo.
echo  ============================================
echo   Seba Sohayok  -  starting
echo  ============================================
echo.

if not exist ".env" (
  echo  [!] .env not found.
  echo      Copy .env.example to .env and put your Gemini API key in it.
  echo.
  pause
  exit /b 1
)

findstr /b /c:"GEMINI_API_KEY=" .env | findstr /v /c:"GEMINI_API_KEY=" >nul 2>&1
findstr /r /c:"^GEMINI_API_KEY=.\+" .env >nul 2>&1
if errorlevel 1 (
  echo  [!] GEMINI_API_KEY is empty in .env
  echo      Open .env and paste your key after the = sign.
  echo.
  pause
  exit /b 1
)

if not exist "data\embeddings.npz" (
  echo  Building the search index ^(first run only^)...
  python -m app.index
  if errorlevel 1 (
    echo.
    echo  [!] Index build failed. Run  python check.py  to see why.
    pause
    exit /b 1
  )
  echo.
)

echo  Opening http://127.0.0.1:8000 in your browser...
start "" http://127.0.0.1:8000
echo  Press Ctrl+C in this window to stop the server.
echo.

python -m uvicorn app.main:app --reload --port 8000

echo.
echo  Server stopped.
pause
