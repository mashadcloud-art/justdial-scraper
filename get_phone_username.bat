@echo off
set ADB_PATH=platform-tools\adb.exe

echo Make sure your Termux cursor is active on the S8 screen.
pause

echo Typing whoami on your S8...
%ADB_PATH% -d shell input text "whoami"
%ADB_PATH% -d shell input keyevent 66

echo.
echo Read the username printed on your phone's Termux screen!
pause
