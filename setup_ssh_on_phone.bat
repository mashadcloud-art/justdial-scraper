@echo off
echo ==============================================
echo Termux SSH Setup Auto-Typer
echo ==============================================
echo.
echo 1. Open the Termux app on your S8.
echo 2. Click inside the Termux screen so the cursor is active.
echo.
pause

set ADB_PATH=platform-tools\adb.exe

echo.
echo [1/3] Installing OpenSSH...
%ADB_PATH% -d shell input text "pkg%%sinstall%%sopenssh%%s-y"
%ADB_PATH% -d shell input keyevent 66

echo.
echo Please wait for OpenSSH to finish installing inside Termux.
echo Once it is done and showing the command prompt, press any key here to continue.
echo.
pause

echo [2/3] Starting SSH Daemon...
%ADB_PATH% -d shell input text "sshd"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [3/3] Getting IP Address and starting password setup...
%ADB_PATH% -d shell input text "ip%%saddr%%sshow%%swlan0%%s|%%sgrep%%sinet"
%ADB_PATH% -d shell input keyevent 66
%ADB_PATH% -d shell input text "passwd"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] Commands sent! 
echo.
echo 1. Check your phone's Termux screen.
echo 2. Type a password for SSH and press Enter (it won't show characters as you type).
echo 3. Confirm the password by typing it again and pressing Enter.
echo 4. Note down the IP address shown on the screen (e.g. 192.168.1.XX).
echo.
pause
