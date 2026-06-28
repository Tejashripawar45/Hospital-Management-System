@echo off
REM Run the HMS application with Chrome auto-launch
REM This script starts the server in the background and opens Chrome

cd /d "c:\Users\pawar\OneDrive\Desktop\TASK1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "run-app.ps1"
pause
