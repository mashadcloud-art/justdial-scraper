@echo off
set ADB_PATH=platform-tools\adb.exe

echo Make sure your Termux cursor is active on the S8 screen.
pause

echo Starting SSH daemon on your S8...
%ADB_PATH% -d shell input text "sshd"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] SSH daemon started! Check your PC dashboard now.
pause
