@echo off
title Mirror Samsung Phone
cd /d "%~dp0"
set SCRCPY_DIR=%~dp0scratch\scrcpy\scrcpy-win64-v4.0
"%SCRCPY_DIR%\scrcpy.exe" -s ce091719ccb730820c
exit
