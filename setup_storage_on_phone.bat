@echo off
echo ==============================================
echo Termux Storage Setup Auto-Typer
echo ==============================================
echo.
echo 1. Open the Termux app on your S8.
echo 2. Click inside the Termux screen so the cursor is active.
echo.
pause

set ADB_PATH=platform-tools\adb.exe

echo Sending storage setup command...
%ADB_PATH% -d shell input text "termux-setup-storage"
%ADB_PATH% -d shell input keyevent 66

echo.
echo Check your phone screen and tap "Allow" when the popup shows.
pause
