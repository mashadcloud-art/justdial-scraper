@echo off
echo ===============================================
echo Starting JustDial Scraper - All in One!
echo ===============================================

REM Change to the project directory
cd /d "%~dp0"

echo 1. Starting FastAPI Backend (port 8000)...
start "FastAPI Server" cmd /k ""C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe" -m uvicorn app.main:app --host localhost --port 8000"

echo 2. Waiting 5 seconds for FastAPI to start...
timeout /t 5 /nobreak >nul

echo 3. Starting Desktop Scraper App...
start "JustDial Scraper" cmd /k ""C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe" ScraperApp.py"

echo.
echo ===============================================
echo All apps are now running!
echo Use the Scraper app for everything!
echo If you want Streamlit Dashboard too, press any key now...
echo ===============================================
pause >nul

echo Starting Streamlit Dashboard (optional)...
start "Streamlit Dashboard" cmd /k ""C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe" -m streamlit run frontend.py --server.port 8502"
