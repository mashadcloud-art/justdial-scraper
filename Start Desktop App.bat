@echo off
echo ===============================================
echo Starting JustDial Pro Scraper!
echo ===============================================
cd /d "%~dp0"
start "" "C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe" ScraperApp.py
timeout /t 3 /nobreak >nul
echo Done! App is running!
