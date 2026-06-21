import os
import subprocess
import time
import random
import argparse
import logging
from typing import List

try:
    from app.scraper.logger import log
except ImportError:
    def log(msg: str, ok: bool = True):
        timestamp = time.strftime("%H:%M:%S")
        try:
            print(f"[{timestamp}] {msg}")
        except UnicodeEncodeError:
            import sys
            encoding = sys.stdout.encoding or 'utf-8'
            safe_msg = msg.encode(encoding, errors='replace').decode(encoding)
            print(f"[{timestamp}] {safe_msg}")

if os.name == "nt":
    ADB_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    ADB_TARGET = ""
else:
    ADB_PATH = "adb"
    ADB_TARGET = "-s localhost:5555"


def run_adb(cmd: str) -> str:
    """Run an ADB shell command."""
    if ADB_TARGET:
        full_cmd = f'"{ADB_PATH}" {ADB_TARGET} shell {cmd}'
    else:
        full_cmd = f'"{ADB_PATH}" shell {cmd}'

    try:
        result = subprocess.check_output(full_cmd, shell=True, text=True)
        return result.strip()
    except subprocess.CalledProcessError as e:
        log(f"ADB command failed: {e}", ok=False)
        return ""

def tap(x: int, y: int):
    """Tap at specific coordinates."""
    log(f"Tapping ({x}, {y})")
    run_adb(f"input tap {x} {y}")

def type_text(text: str):
    """Type text simulating a human keyboard."""
    log(f"Typing: {text}")
    # Replace spaces with %s for ADB input text
    encoded_text = text.replace(" ", "%s")
    run_adb(f"input text '{encoded_text}'")

def press_enter():
    """Press the Enter/Search key."""
    log("Pressing ENTER")
    run_adb("input keyevent 66")

def go_back():
    """Press the Back button."""
    log("Pressing BACK")
    run_adb("input keyevent 4")

def swipe_up(duration_ms=1000):
    """Swipe up to scroll down the page."""
    log("Swiping up...")
    run_adb(f"input swipe 500 1500 500 300 {duration_ms}")

def human_delay(min_sec=1.0, max_sec=2.5):
    """Sleep for a random amount of time to simulate a human."""
    sleep_time = random.uniform(min_sec, max_sec)
    time.sleep(sleep_time)

def automate_location_search(locations: List[str], category: str, scrolls: int):
    log(f"Starting targeted search for {len(locations)} locations.")
    
    # Ensure the JustDial app is launched and active
    log("Launching JustDial app...")
    run_adb("monkey -p com.justdial.search -c android.intent.category.LAUNCHER 1")
    time.sleep(4.0)
    
    for i, loc in enumerate(locations):
        log(f"=== [Location {i+1}/{len(locations)}] Setting Location: {loc} ===")
        
        # 0. Start on Home Page: Tap search bar (X=400, Y=170) to open the search screen
        tap(400, 170)
        human_delay(1.5, 2.0)
        
        # 1. Tap location header (X=450, Y=62) to open Select Location screen
        tap(450, 62)
        human_delay(1.5, 2.0)
        
        # 2. Tap location search input box (X=450, Y=150) to focus
        tap(450, 150)
        human_delay(0.8, 1.2)
        
        # 3. Type the location (PIN code / Town)
        type_text(loc)
        human_delay(2.5, 3.5) # Wait for suggestions to load
        
        # 4. Tap the first suggestion (usually below divider, X=450, Y=350)
        tap(450, 350)
        human_delay(2.0, 3.0) # Wait for UI to update and return to search screen
        
        # 5. Tap the category search input box (X=450, Y=150) to focus
        tap(450, 150)
        human_delay(0.8, 1.2)
        
        # 6. Type category name (e.g. Restaurants)
        type_text(category)
        human_delay(0.8, 1.2)
        
        # 7. Press Enter to execute search
        press_enter()
        human_delay(4.0, 6.0) # Wait for search results to load
        
        # 8. Scroll down to trigger database requests
        for s in range(1, scrolls + 1):
            log(f"Scroll {s}/{scrolls} for '{category} in {loc}'")
            swipe_up(duration_ms=random.randint(600, 1000))
            human_delay(1.2, 2.0)
            
        # 9. Press BACK twice to return to home search screen for next query
        go_back()
        human_delay(1.5, 2.0)
        go_back()
        human_delay(2.0, 3.0)
        
    log("Location-based search automation complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Targeted Location ADB Automator for JustDial")
    parser.add_argument("--locations", nargs="+", required=True, help="List of PIN codes or town names")
    parser.add_argument("--category", default="Restaurants", help="Category to search (default: Restaurants)")
    parser.add_argument("--scrolls", type=int, default=15, help="Number of scrolls per search")
    args = parser.parse_args()
    
    automate_location_search(args.locations, args.category, args.scrolls)
