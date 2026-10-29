@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Seba Sohayok - rebuild search index

echo.
echo  Rebuilding the search index from data\*.json ...
echo  Run this after editing the knowledge base or its keywords.
echo.

if exist "data\embeddings.npz" del /q "data\embeddings.npz"
python -m app.index

echo.
pause
