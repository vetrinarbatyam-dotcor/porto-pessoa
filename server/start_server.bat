@echo off
rem PESSOA Control Server launcher — double-click to start.
cd /d "%~dp0\.."
start "PESSOA Server" ".venv\Scripts\python.exe" "server\app.py"
timeout /t 2 /nobreak >nul
start "" "dashboard\out\index.html"
