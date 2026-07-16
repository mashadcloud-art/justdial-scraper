@echo off
echo ==============================================
echo Termux config.yaml Writer
echo ==============================================
echo.
echo This will write your Supabase URL directly to config.yaml on your phone
echo to avoid the Pydantic .env error.
echo.
echo 1. Open the Termux app on your S8.
echo 2. Make sure the Termux cursor is active and blinking.
echo.
pause

set ADB_PATH=platform-tools\adb.exe

echo Sending config.yaml creation command...
:: Write the database url to config.yaml
%ADB_PATH% -d shell input text "cat%%s^<^<%%s'EOF'%%s^>%%sconfig.yaml"
%ADB_PATH% -d shell input keyevent 66
%ADB_PATH% -d shell input text "database:"
%ADB_PATH% -d shell input keyevent 66
%ADB_PATH% -d shell input text "%%s%%surl:%%spostgresql://postgres:HEERnuh%%402025@db.qdsjbfhjzyypfyryjqxp.supabase.co:5432/postgres"
%ADB_PATH% -d shell input keyevent 66
%ADB_PATH% -d shell input text "EOF"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] config.yaml written to your S8!
pause
