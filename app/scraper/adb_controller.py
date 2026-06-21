import os
import time
import subprocess
import argparse
from app.scraper.logger import log

if os.name == "nt":
    ADB_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
else:
    ADB_PATH = "adb"


def swipe_up(device="emulator-5554"):
    """
    Simulates a finger swipe up on the screen (scrolling down).
    Coordinates may need adjusting based on emulator resolution.
    """
    try:
        # Swipe from bottom-center to top-center
        subprocess.run(
            [ADB_PATH, "-s", device, "shell", "input", "swipe", "500", "1500", "500", "400", "300"],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        log(f"ADB swipe failed: {e.stderr.decode()}", ok=False)
        return False

def auto_scroll_loop(interval=3.0, max_swipes=1000):
    """
    Continuously scrolls the emulator to load more data.
    """
    log("🚀 Starting ADB Auto-Scroller for BlueStacks...")
    log("   (Press Ctrl+C to stop)")
    try:
        for i in range(1, max_swipes + 1):
            log(f"  👆 Swipe {i}/{max_swipes}")
            if not swipe_up():
                log("⚠️ Stopping auto-scroll due to error.", ok=False)
                break
            time.sleep(interval)
        log("🏁 Auto-scroll complete.")
    except KeyboardInterrupt:
        log("\n🛑 Auto-scroll stopped by user.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-scroll BlueStacks for JustDial scraping")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds to wait between swipes")
    parser.add_argument("--max-swipes", type=int, default=1000, help="Maximum number of swipes before stopping")
    args = parser.parse_args()
    
    auto_scroll_loop(interval=args.interval, max_swipes=args.max_swipes)
