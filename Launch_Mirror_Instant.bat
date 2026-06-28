@echo off
title JustDial Scraper - Local Screen Mirror
cd /d "%~dp0"

set SCRCPY_DIR=%~dp0scratch\scrcpy\scrcpy-win64-v4.0
set ADB=%SCRCPY_DIR%\adb.exe
set SCRCPY=%SCRCPY_DIR%\scrcpy.exe

set TARGET_DEVICE=100.110.105.12:5555
if exist "data\active_device.txt" (
    set /p TARGET_DEVICE=<"data\active_device.txt"
)

echo [*] Starting ADB server ...
"%ADB%" start-server >nul 2>&1

echo [*] Checking connection to %TARGET_DEVICE% ...
echo %TARGET_DEVICE% | findstr /C:":" >nul
if %errorlevel% equ 0 (
    "%ADB%" connect %TARGET_DEVICE% >nul 2>&1
)

echo [*] Launching scrcpy screen mirror for %TARGET_DEVICE% ...
start "" "%SCRCPY%" -s %TARGET_DEVICE%
exit
