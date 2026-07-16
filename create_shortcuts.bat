@echo off
echo ==============================================
echo Creating Desktop Shortcuts (Silent mode)
echo ==============================================
echo.

powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $S1 = $WshShell.CreateShortcut('C:\Users\PC\Desktop\Mirror S8 (USB).lnk'); $S1.TargetPath = 'C:\Users\PC\Documents\trae_projects\Scapre for thozil\launch_scrcpy_usb_silent.vbs'; $S1.WorkingDirectory = 'C:\Users\PC\Documents\trae_projects\Scapre for thozil'; $S1.Save(); $S2 = $WshShell.CreateShortcut('C:\Users\PC\Desktop\Mirror S8 (Wireless).lnk'); $S2.TargetPath = 'C:\Users\PC\Documents\trae_projects\Scapre for thozil\launch_scrcpy_wireless_silent.vbs'; $S2.WorkingDirectory = 'C:\Users\PC\Documents\trae_projects\Scapre for thozil'; $S2.Save()"

echo [SUCCESS] Desktop shortcuts created!
pause
