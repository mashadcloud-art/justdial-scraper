import threading
import uvicorn
import sys
import os
import time

# Ensure project root is in python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def start_backend():
    """Start the FastAPI backend server in a background thread"""
    try:
        from config import settings
        # Run uvicorn on localhost to avoid Windows network permission popups
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")
    except Exception as e:
        print(f"Failed to start FastAPI backend: {e}")

if __name__ == "__main__":
    # 1. Start backend server in a daemon thread
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()
    
    # Give uvicorn a moment to bind to the port
    time.sleep(1)
    
    # 2. Import and start the Tkinter desktop app
    # Rename ModernScraperApp.pyw import to match standard module loading
    from ModernScraperApp import main as run_gui
    run_gui()
