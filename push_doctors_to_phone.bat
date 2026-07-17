@echo off
echo ==============================================
echo Sync and Launch Doctors Scraper on Phone
echo ==============================================
echo.

set ADB_PATH=platform-tools\adb.exe

echo [1/3] Pushing files to SD Card...
%ADB_PATH% -d push jd_api_scraper.py /sdcard/jd_api_scraper.py
%ADB_PATH% -d push scrape_kerala_doctors.py /sdcard/scrape_kerala_doctors.py
%ADB_PATH% -d push app/api/pincodes.py /sdcard/pincodes.py

echo.
echo [2/3] Preparing Termux synchronization...
echo 1. Open the Termux app on your S8.
echo 2. Click inside the Termux screen so the cursor is active.
echo.
pause

echo Copying updated files inside Termux...
%ADB_PATH% -d shell input text "cp%%s/sdcard/jd_api_scraper.py%%s~/justdial-scraper/jd_api_scraper.py"
%ADB_PATH% -d shell input keyevent 66

%ADB_PATH% -d shell input text "cp%%s/sdcard/scrape_kerala_doctors.py%%s~/justdial-scraper/scrape_kerala_doctors.py"
%ADB_PATH% -d shell input keyevent 66

%ADB_PATH% -d shell input text "mkdir%%s-p%%s~/justdial-scraper/app/api"
%ADB_PATH% -d shell input keyevent 66

%ADB_PATH% -d shell input text "cp%%s/sdcard/pincodes.py%%s~/justdial-scraper/app/api/pincodes.py"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [3/3] Starting Scraper in Termux...
%ADB_PATH% -d shell input text "cd%%s~/justdial-scraper"
%ADB_PATH% -d shell input keyevent 66

%ADB_PATH% -d shell input text "python%%sscrape_kerala_doctors.py"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] Script synced and launched in Termux!
echo Keep your phone screen on while it runs.
pause
