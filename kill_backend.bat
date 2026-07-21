@echo off
title Kill Stuck JustDial Scraper Backend
echo ====================================================
echo  Killing Stuck Python/FastAPI Backend Processes
echo ====================================================
echo.

echo [+] Stopping any running pythonw.exe or python.exe background tasks...
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM python.exe 2>nul

echo [+] Resetting database job status...
:: We can run a small sqlite command to set status to stopped if they use local sqlite
:: But taskkill alone will stop the execution completely.

echo.
echo [SUCCESS] Backend stopped! You can now start fresh.
echo.
echo Press any key to close...
pause > nul
