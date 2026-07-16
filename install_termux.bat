@echo off
echo ==============================================
echo Termux Installer via ADB for Galaxy S8
echo ==============================================
echo.

:: Define local adb path
set ADB_PATH=adb
set LOCAL_ADB=platform-tools\adb.exe

:: Check if ADB is in system PATH
where adb >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Found system-wide ADB.
    set ADB_PATH=adb
    goto check_device
)

:: Check if local ADB is already downloaded
if exist "%LOCAL_ADB%" (
    echo [INFO] Found local ADB in platform-tools.
    set ADB_PATH="%LOCAL_ADB%"
    goto check_device
)

:: Download ADB locally
echo [INFO] ADB not found. Downloading Android Platform Tools...
powershell -Command "Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile 'platform-tools.zip'"
if not exist platform-tools.zip (
    echo [ERROR] Failed to download Android platform-tools.
    pause
    exit /b
)

echo [INFO] Extracting Platform Tools...
powershell -Command "Expand-Archive -Path 'platform-tools.zip' -DestinationPath '.' -Force"
del platform-tools.zip

if not exist "%LOCAL_ADB%" (
    echo [ERROR] Extraction failed or adb.exe not found.
    pause
    exit /b
)

echo [SUCCESS] Local ADB ready!
set ADB_PATH="%LOCAL_ADB%"

:check_device
echo.
echo Checking for connected Android devices...
%ADB_PATH% devices
echo.
echo If your device shows as "unauthorized" or doesn't appear, please:
echo 1. Ensure USB Debugging is turned on in your phone's Developer Options.
echo 2. Unlock your phone and accept the "Allow USB Debugging" prompt.
echo.
pause

:: 3. Download Termux APK
if not exist termux.apk (
    echo Downloading Termux v0.118.3 APK arm64-v8a...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/termux/termux-app/releases/download/v0.118.3/termux-app_v0.118.3+github-debug_arm64-v8a.apk' -OutFile 'termux.apk'"
)

if not exist termux.apk (
    echo [ERROR] Download failed. Please download the APK manually from:
    echo https://github.com/termux/termux-app/releases/download/v0.118.3/termux-app_v0.118.3+github-debug_arm64-v8a.apk
    pause
    exit /b
)

:: 4. Install the APK
echo.
echo Installing Termux on your S8...
%ADB_PATH% install -r termux.apk
if %errorlevel%==0 (
    echo.
    echo [SUCCESS] Termux has been successfully installed on your Galaxy S8!
    del termux.apk
) else (
    echo.
    echo [ERROR] Installation failed. Make sure your phone screen is unlocked and USB debugging is allowed.
)

pause
