import time
import random
import os
import subprocess

def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

ADB_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
DEVICE = "127.0.0.1:5556"  # BlueStacks only

def run_adb(cmd):
    try:
        full_cmd = f'"{ADB_PATH}" -s {DEVICE} shell {cmd}'
        subprocess.run(full_cmd, shell=True, check=True)
    except Exception as e:
        log(f"ADB command failed: {e}")

def swipe_up(duration_ms=1000):
    run_adb(f"input swipe 500 1500 500 300 {duration_ms}")

def human_delay(min_sec=1.0, max_sec=2.5):
    time.sleep(random.uniform(min_sec, max_sec))

def main():
    log("Running Test Deep Link for Hospitals in Kasaragod (671121)...")
    
    # Wake up screen
    run_adb("input keyevent KEYCODE_WAKEUP")
    run_adb("input keyevent 82")
    human_delay(1, 2)
    
    # Force stop JustDial
    run_adb("am force-stop com.justdial.search")
    human_delay(2, 3)
    
    # Start via Deep Link
    url = "https://www.justdial.com/671121/Hospitals"
    log(f"Launching Intent View: {url}")
    run_adb(f'am start -W -a android.intent.action.VIEW -d "{url}"')
    
    # Wait for results to load
    log("Waiting 10 seconds for page to load...")
    time.sleep(10)
    
    # Scroll 5 times to trigger proxy capture
    for s in range(1, 6):
        log(f"Scroll {s}/5...")
        swipe_up(duration_ms=random.randint(600, 1000))
        human_delay(1.5, 2.5)
        
    log("Test complete!")

if __name__ == "__main__":
    main()
