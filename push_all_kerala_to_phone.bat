@echo off
echo ==============================================
echo Pushing All-Kerala Scraper to S8
echo ==============================================
echo.

set ADB_PATH=platform-tools\adb.exe

echo [1/3] Pushing shell script to SD card...
%ADB_PATH% -d push scrape_all_kerala.sh /sdcard/scrape_all_kerala.sh

echo.
echo [2/3] Preparing Termux synchronization...
echo 1. Open the Termux app on your S8.
echo 2. Click inside the Termux screen so the cursor is active.
echo.
pause

echo Moving file inside Termux and changing permissions...
%ADB_PATH% -d shell input text "cp%%s/sdcard/scrape_all_kerala.sh%%s~/scrape_all_kerala.sh"
%ADB_PATH% -d shell input keyevent 66
%ADB_PATH% -d shell input text "chmod%%s+x%%s~/scrape_all_kerala.sh"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [3/3] Starting Scraper in background (nohup)...
%ADB_PATH% -d shell input text "nohup%%s~/scrape_all_kerala.sh%%s^\u003e%%s~/scrape_all.log%%s2^\u00261%%s^\u0026"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] Script is now running in the background on your S8!
echo You can disconnect the USB. It will save outputs to ~/scrape_all.log
pause
