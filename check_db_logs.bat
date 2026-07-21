@echo off
title Check Database Scraper Logs
cd /d "%~dp0"
echo ====================================================
echo  Latest Deep Scraper Logs from Database
echo ====================================================
echo.
C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe check_db_logs.py
echo.
echo Press any key to close...
pause > nul
