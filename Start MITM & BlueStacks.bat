@echo off
title JustDial Scraper MITM & BlueStacks Activator
cd /d "%~dp0"
echo Starting MITM Proxy and setting up BlueStacks ADB proxy...
call venv\Scripts\python.exe start_mitm.py
pause
