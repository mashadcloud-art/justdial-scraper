@echo off
echo ==============================================
echo Phone Scraper Launcher
echo ==============================================
echo.

set /p DISTRICT="Enter District (e.g. Ernakulam): "
set /p CATEGORY="Enter Category (e.g. Doctors): "
set /p PAGES="Enter Number of Pages (e.g. 5): "

set ADB_PATH=platform-tools\adb.exe

echo.
echo 1. Open the Termux app on your S8.
echo 2. Click inside the Termux screen so the cursor is active.
echo.
pause

echo Sending run command to Termux...
%ADB_PATH% -d shell input text "python%%sjd_api_scraper.py%%s--district%%s%DISTRICT%%%s--category%%s\"%CATEGORY%\"%%s--pages%%s%PAGES%"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] Command sent to Termux!
pause
