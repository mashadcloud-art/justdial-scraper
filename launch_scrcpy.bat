@echo off
echo ==============================================
echo Screen Mirroring (scrcpy) Launcher for Galaxy S8
echo ==============================================
echo.

:: Define paths
set SCRCPY_DIR=scrcpy-win64-v4.1
set LOCAL_SCRCPY=%SCRCPY_DIR%\scrcpy.exe

:: Check if scrcpy is already downloaded
if exist "%LOCAL_SCRCPY%" (
    echo [INFO] Found local scrcpy.
    goto run_scrcpy
)

:: Download scrcpy
echo [INFO] scrcpy not found. Downloading scrcpy-win64 v4.1...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/Genymobile/scrcpy/releases/download/v4.1/scrcpy-win64-v4.1.zip' -OutFile 'scrcpy.zip'"
if not exist scrcpy.zip (
    echo [ERROR] Failed to download scrcpy.
    pause
    exit /b
)

echo [INFO] Extracting scrcpy...
powershell -Command "Expand-Archive -Path 'scrcpy.zip' -DestinationPath '.' -Force"
del scrcpy.zip

if not exist "%LOCAL_SCRCPY%" (
    echo [ERROR] Extraction failed or scrcpy.exe not found.
    pause
    exit /b
)

echo [SUCCESS] scrcpy is ready!

:run_scrcpy
echo.
echo Launching Screen Mirroring...
echo (Ensure your S8 is unlocked and connected)
echo.
cd "%SCRCPY_DIR%"
scrcpy.exe --window-title "Galaxy S8 Screen"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] scrcpy exited with an error. 
    echo Please make sure your S8 is unlocked, connected via USB, and USB debugging is allowed.
    pause
)
