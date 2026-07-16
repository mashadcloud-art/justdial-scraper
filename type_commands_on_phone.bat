@echo off
echo ==============================================
echo Termux Command Auto-Typer
echo ==============================================
echo.
echo 1. Open the Termux app on your S8 phone.
echo 2. Click inside the Termux screen so your cursor is active and blinking.
echo.
pause

set ADB_PATH=platform-tools\adb.exe

echo.
echo [1/2] Sending package install command (clang and postgresql)...
:: %s is a space. We target the USB device (-d)
%ADB_PATH% -d shell input text "pkg%%sinstall%%sclang%%spostgresql%%s-y"
%ADB_PATH% -d shell input keyevent 66

echo.
echo Please wait for the clang/postgresql installation to finish inside Termux.
echo Once it is done and showing a new command prompt, press any key here to send the next command.
echo.
pause

echo [2/2] Sending pip installation command (sqlalchemy and psycopg2)...
%ADB_PATH% -d shell input text "pip%%sinstall%%ssqlalchemy%%spsycopg2"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] Both commands have been typed and sent to your phone!
pause
