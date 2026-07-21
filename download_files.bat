@echo off
title Download Files from Cloud (thozil)
cd /d "%~dp0"
echo ====================================================
echo  Downloading Cloud App from 'thozil' (Port 3000)
echo ====================================================
echo.
C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe download_files.py
echo.
echo Press any key to close...
pause > nul
