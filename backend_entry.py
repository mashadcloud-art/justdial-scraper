"""
Scapre Pro — Backend Entry Point
Launched by PyInstaller as backend.exe
"""
import sys
import os
import argparse

# Parse CLI args
parser = argparse.ArgumentParser()
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8000)
args, _ = parser.parse_known_args()

# In PyInstaller, the exe lives in resources/ folder.
# sys.executable = path to backend.exe
# We set cwd to the folder containing the exe (resources/)
exe_dir = os.path.dirname(os.path.abspath(sys.executable))
os.chdir(exe_dir)
sys.path.insert(0, exe_dir)

print(f"[Backend] Working directory: {os.getcwd()}")
print(f"[Backend] ui/dist/client exists: {os.path.exists('ui/dist/client')}")
print(f"[Backend] index.html exists: {os.path.exists('ui/dist/client/index.html')}")

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=False,
        workers=1,
        log_level="info",
    )
