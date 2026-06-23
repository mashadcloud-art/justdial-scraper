@echo off
cd /d "%~dp0"
echo Starting JustDial Pro Scraper backend and frontend...
start "" pythonw run_app.py
exit
