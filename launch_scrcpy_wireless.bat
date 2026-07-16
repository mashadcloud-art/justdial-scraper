@echo off
echo ==============================================
echo Wireless scrcpy Connector for Galaxy S8
echo ==============================================
echo.

:: Define paths
set LOCAL_ADB=platform-tools\adb.exe
set SCRCPY_DIR=scrcpy-win64-v4.1
set LOCAL_SCRCPY=%SCRCPY_DIR%\scrcpy.exe

:: Validate prerequisites
if not exist "%LOCAL_ADB%" (
    echo [ERROR] Local ADB not found. Please run launch_scrcpy.bat first to set it up.
    pause
    exit /b
)
if not exist "%LOCAL_SCRCPY%" (
    echo [ERROR] scrcpy not found. Please run launch_scrcpy.bat first to download it.
    pause
    exit /b
)

set ADB_PATH="%CD%\platform-tools\adb.exe"

echo 1. Ensure your S8 and your PC are on the SAME Wi-Fi network.
echo 2. Make sure your S8 is PLUGGED IN via USB cable.
echo.
pause

:: Auto-detect IP address while plugged in via USB (force USB target with -d)
echo Detecting phone's IP address...
for /f "usebackq tokens=*" %%a in (`powershell -Command "$adb = '%CD%\platform-tools\adb.exe'; $out = & $adb -d shell ip route; $ip = [regex]::match($out, 'src\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})').Groups[1].Value; if (-not $ip) { $out2 = & $adb -d shell ip addr show wlan0; $ip = [regex]::match($out2, 'inet\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})').Groups[1].Value }; $ip"`) do set IP=%%a

if "%IP%"=="" (
    echo [WARNING] Could not auto-detect your IP address.
    set /p IP="Please enter your phone's IP address manually (from Settings -> About -> Status): "
) else (
    echo [SUCCESS] Auto-detected Phone IP: %IP%
)

:: Save IP address to file for silent launcher
echo %IP% > ip.txt

echo.
echo Enabling ADB wireless mode (TCP/IP port 5555)...
%ADB_PATH% -d tcpip 5555
if %errorlevel% neq 0 (
    echo [ERROR] Failed to set TCP/IP port. Is your phone connected via USB?
    pause
    exit /b
)
echo.
echo [SUCCESS] Wireless mode enabled!
echo --- YOU CAN NOW UNPLUG THE USB CABLE ---
echo.
pause

echo Connecting to %IP%...
%ADB_PATH% connect %IP%:5555
if %errorlevel% neq 0 (
    echo [ERROR] Failed to connect to %IP% wirelessly.
    pause
    exit /b
)

echo.
echo Launching Screen Mirroring Wirelessly...
cd "%SCRCPY_DIR%"
scrcpy.exe -e --window-title "Galaxy S8 (Wireless)"
pause
