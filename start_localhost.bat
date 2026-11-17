@echo off
chcp 65001 >nul
title Enterprise Data Analytics AI Agent - Localhost Server (Port 8080)
echo Đang khởi động AI Agent Localhost Server tại http://localhost:8080 ...
start "" "http://localhost:8080"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0server.ps1" -Port 8080
pause
