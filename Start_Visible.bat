@echo off
title JustDial Scraper Launcher (Visible)
cd /d "C:\Users\PC\Documents\trae_projects\Scapre for thozil"

echo Starting FastAPI Backend...
start "FastAPI Backend" cmd /k "C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo Starting Vite Frontend...
start "Vite Frontend" cmd /k "cd ui && npm run dev"

echo Starting Streamlit Dashboard...
start "Streamlit Dashboard" cmd /k "C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe -m streamlit run frontend.py"

echo Waiting 5 seconds for servers to start...
ping -n 6 127.0.0.1 >nul

echo Opening browser...
start http://localhost:5173

echo All servers started and browser opened!
