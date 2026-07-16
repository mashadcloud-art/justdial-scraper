@echo off
echo ==============================================
echo Termux Backend Library Installer
echo ==============================================
echo.
echo 1. Make sure your Termux cursor is active and blinking.
echo.
pause

set ADB_PATH=platform-tools\adb.exe

echo.
echo Sending pip command for backend libraries...
%ADB_PATH% -d shell input text "pip%%sinstall%%sfastapi%%suvicorn%%spydantic%%spydantic-settings%%spyyaml%%spyjwt%%srequests%%saiohttp"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] Typed! Wait for pip to finish the installation.
pause
