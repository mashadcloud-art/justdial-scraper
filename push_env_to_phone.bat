@echo off
echo ==============================================
echo Termux .env Installer (Direct File Sync)
echo ==============================================
echo.

set LOCAL_ENV=temp_env_file.env
set ADB_PATH=platform-tools\adb.exe

:: Create the .env file locally on PC with both cases to ensure Pydantic reads it
echo database_url=postgresql://postgres.qdsjbfhjzyypfyryjqxp:HEERnuh%%402025@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres > "%LOCAL_ENV%"
echo DATABASE_URL=postgresql://postgres.qdsjbfhjzyypfyryjqxp:HEERnuh%%402025@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres >> "%LOCAL_ENV%"

echo Pushing .env configuration to S8 storage...
%ADB_PATH% -d push "%LOCAL_ENV%" /sdcard/.env
if %errorlevel% neq 0 (
    echo [ERROR] Failed to push .env file. Is your phone connected via USB?
    del "%LOCAL_ENV%"
    pause
    exit /b
)

:: Clean up local temporary file
del "%LOCAL_ENV%"

echo.
echo 1. Open the Termux app on your S8.
echo 2. Click inside the Termux screen so the cursor is active.
echo.
pause

echo Copying .env into your scraper folder...
%ADB_PATH% -d shell input text "cp%%s/sdcard/.env%%s~/justdial-scraper/.env"
%ADB_PATH% -d shell input keyevent 66

echo.
echo [SUCCESS] Database configuration successfully installed on S8!
pause
