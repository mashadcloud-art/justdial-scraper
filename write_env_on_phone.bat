@echo off
echo ==============================================
echo Termux .env Writer
echo ==============================================
echo.
echo 1. Open the Termux app on your S8.
echo 2. Click inside the Termux screen so the cursor is active.
echo.
pause

set ADB_PATH=platform-tools\adb.exe

echo Writing .env file on phone...
%ADB_PATH% -d shell input text "echo%%s\"DATABASE_URL=postgresql://postgres:HEERnuh%%402025@db.qdsjbfhjzyypfyryjqxp.supabase.co:5432/postgres\"%%s^>%%s.env"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] .env file written on your phone!
pause
