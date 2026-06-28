import threading
import uvicorn
import sys
import os
import time
import subprocess
import webbrowser
import re
import urllib.request

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

UI_DIR = os.path.join(project_root, "ui")
APP_W, APP_H = 1024, 640
_vite_url = None

def start_backend():
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")
    except Exception:
        pass

def wait_for_backend(timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False

def start_vite():
    global _vite_url
    try:
        proc = subprocess.Popen(
            "npm run dev",
            cwd=UI_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            text=True
        )
        for line in proc.stdout:
            if _vite_url is None:
                m = re.search(r"Local:\s+(http://localhost:\d+)", line)
                if m:
                    _vite_url = m.group(1)
        proc.wait()
    except Exception:
        pass

def open_app(url):
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    args = [
        "--app=" + url,
        "--window-size=" + str(APP_W) + "," + str(APP_H),
        "--window-position=200,80",
        "--disable-extensions",
        "--no-first-run",
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            subprocess.Popen([path] + args)
            return
    webbrowser.open(url)

if __name__ == "__main__":
    # 1. Start backend
    threading.Thread(target=start_backend, daemon=True).start()
    
    # 2. Start Vite
    threading.Thread(target=start_vite, daemon=True).start()

    # 3. Wait for backend to be ready
    wait_for_backend(timeout=30)

    # 4. Wait for Vite URL
    start = time.time()
    while _vite_url is None and (time.time() - start) < 60:
        time.sleep(0.3)

    time.sleep(1)
    open_app(_vite_url or "http://localhost:5173")

    # 5. Keep alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
