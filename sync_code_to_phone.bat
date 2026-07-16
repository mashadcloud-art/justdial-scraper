@echo off
echo ==============================================
echo Code Syncer to Phone (Termux)
echo ==============================================
echo.

set ADB_PATH=platform-tools\adb.exe

echo Pushing updated files to phone storage...
%ADB_PATH% -d push config.py /sdcard/config.py
if %errorlevel% neq 0 (
    echo [ERROR] Failed to push config.py.
    pause
    exit /b
)
%ADB_PATH% -d push run_deep_scraper.py /sdcard/run_deep_scraper.py
if %errorlevel% neq 0 (
    echo [ERROR] Failed to push run_deep_scraper.py.
    pause
    exit /b
)

echo.
echo 1. Open the Termux app on your S8.
echo 2. Click inside the Termux screen so the cursor is active.
echo.
pause

echo Copying updated files into your project folder...
%ADB_PATH% -d shell input text "cp%%s/sdcard/config.py%%s~/justdial-scraper/config.py"
%ADB_PATH% -d shell input keyevent 66
%ADB_PATH% -d shell input text "cp%%s/sdcard/run_deep_scraper.py%%s~/justdial-scraper/run_deep_scraper.py"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] Files successfully updated on your phone!
pause
