import os
import time
import subprocess
import argparse
from app.scraper.logger import log

if os.name == "nt":
    scrcpy_adb = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scratch", "scrcpy", "scrcpy-win64-v4.0", "adb.exe"))
    if os.path.exists(scrcpy_adb):
        ADB_PATH = scrcpy_adb
    else:
        bluestacks_adb = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
        ADB_PATH = bluestacks_adb if os.path.exists(bluestacks_adb) else os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
else:
    ADB_PATH = "adb"


def _detect_device():
    """Detect the active ADB device from active_device.txt or fallback to the first connected device."""
    try:
        active_device_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "active_device.txt"))
        if os.path.exists(active_device_path):
            with open(active_device_path, "r") as f:
                device = f.read().strip()
                if device:
                    return device
    except Exception:
        pass

    try:
        out = subprocess.check_output(f'"{ADB_PATH}" devices', shell=True, text=True, stderr=subprocess.DEVNULL)
        devices = []
        for line in out.strip().splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        if devices:
            return devices[0]
    except Exception:
        pass

    return "emulator-5554"


def swipe_up(device=None):
    """
    Simulates a finger swipe up on the screen (scrolling down).
    Coordinates may need adjusting based on emulator resolution.
    """
    if device is None:
        device = _detect_device()
        
    try:
        # Swipe from bottom to top on the extreme left edge (X=10) with 2000ms duration to avoid clicking cards
        subprocess.run(
            [ADB_PATH, "-s", device, "shell", "input", "swipe", "10", "1500", "10", "400", "2000"],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        log(f"ADB swipe failed: {e.stderr.decode()}", ok=False)
        return False

def auto_scroll_loop(interval=3.0, max_swipes=1000):
    """
    Continuously scrolls the emulator/device to load more data.
    """
    target_device = _detect_device()
    log(f"🚀 Starting ADB Auto-Scroller for device: {target_device}...")
    log("   (Press Ctrl+C to stop)")
    try:
        for i in range(1, max_swipes + 1):
            log(f"  👆 Swipe {i}/{max_swipes}")
            if not swipe_up(device=target_device):
                log("⚠️ Stopping auto-scroll due to error.", ok=False)
                break
            time.sleep(interval)
        log("🏁 Auto-scroll complete.")
    except KeyboardInterrupt:
        log("\n🛑 Auto-scroll stopped by user.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-scroll BlueStacks/Android Device for JustDial scraping")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds to wait between swipes")
    parser.add_argument("--max-swipes", type=int, default=1000, help="Maximum number of swipes before stopping")
    args = parser.parse_args()
    
    auto_scroll_loop(interval=args.interval, max_swipes=args.max_swipes)

