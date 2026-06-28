@echo off
cd /d "%~dp0"
title JustDial Scraper Launcher

echo ===================================================
echo Starting JustDial Scraper (Backend + Frontend)...
echo ===================================================
echo.
echo [1/3] Terminating any old zombie processes...
powershell -Command "$p8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; if ($p8000) { Stop-Process -Id $p8000.OwningProcess -Force -ErrorAction SilentlyContinue }"
powershell -Command "$p8080 = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue; if ($p8080) { Stop-Process -Id $p8080.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo.
echo [2/3] Starting Backend (FastAPI)...
start /d "%~dp0" /b "" "C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning

echo.
echo [3/3] Starting Frontend (Vite)...
start /d "%~dp0ui" /b "" npm run preview

echo.
echo Waiting for servers to initialize...
ping 127.0.0.1 -n 3 >nul

echo.
echo Launching Web Browser...
start http://127.0.0.1:8080

echo.
echo ===================================================
echo App is running! Keep this window open.
echo To close the app, simply close this window.
echo ===================================================
echo.
cmd /k
