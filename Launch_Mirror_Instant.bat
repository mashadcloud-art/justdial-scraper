@echo off
title JustDial Scraper - Local Screen Mirror
cd /d "%~dp0"

set SCRCPY_DIR=scratch\scrcpy\scrcpy-win64-v4.0
set ADB="%SCRCPY_DIR%\adb.exe"
set SCRCPY="%SCRCPY_DIR%\scrcpy.exe"

set TARGET_DEVICE=100.110.105.12:5555
if exist "data\active_device.txt" (
    set /p TARGET_DEVICE=<"data\active_device.txt"
)

echo [*] Connecting to %TARGET_DEVICE% ...
%ADB% connect %TARGET_DEVICE%

echo [*] Starting scrcpy screen mirror ...
start "" %SCRCPY% -s %TARGET_DEVICE%
exit
