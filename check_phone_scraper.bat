@echo off
title Check Phone Scraper Status
cd /d "%~dp0"
echo ====================================================
echo  Checking Active Scrapers on Phone (Termux)
echo ====================================================
echo.

set ADB_PATH=platform-tools\adb.exe

:: Check if ADB can see the device
%ADB_PATH% devices | findstr /R "\<device\>" >nul
if %errorlevel% neq 0 (
    echo [WARNING] No ADB device detected.
    echo Please make sure your phone is connected via USB with USB Debugging enabled,
    echo or that you are connected wirelessly.
    echo.
    pause
    exit /b
)

echo [+] Phone connected. Checking for running Python/Scraper processes...
echo.

:: We query processes in termux (termux runs under its own user, usually named u0_a...)
:: Using ps -A or ps -ef
echo Running processes on phone matching 'python':
echo ----------------------------------------------------
%ADB_PATH% -d shell "ps -A | grep python"
echo ----------------------------------------------------
echo.
echo If you see processes listed above (e.g. python, python3, jd_api_scraper.py), 
echo then the scraper is STILL RUNNING.
echo.
echo If it is empty, the scraper has FINISHED or stopped.
echo.
echo Press any key to close...
pause > nul
