@echo off
echo ==============================================
echo Phone Deep Scraper Launcher
echo ==============================================
echo.

set /p URL="Enter JustDial Category URL (e.g. https://www.justdial.com/Ernakulam/Doctors): "
set /p MODE="Enter Mode (district or state) [default: district]: "
if "%MODE%"=="" set MODE=district

set ADB_PATH=platform-tools\adb.exe

echo.
echo 1. Open the Termux app on your S8.
echo 2. Click inside the Termux screen so the cursor is active.
echo.
pause

echo Sending deep scraper command to Termux...
:: Send the run command to Termux
%ADB_PATH% -d shell input text "python%%srun_deep_scraper.py%%s--url%%s\"%URL%\"%%s--mode%%s%MODE%"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] Deep Scraper command sent to Termux!
pause
