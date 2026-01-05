@echo off
cd /d "%~dp0"

REM Ferme toute instance précédente
taskkill /IM agent.exe /F >nul 2>&1

timeout /t 2 >nul

REM Lance l’agent (avec systray si user interactif)
start "" agent.exe
