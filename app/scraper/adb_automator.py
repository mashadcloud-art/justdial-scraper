import subprocess
import time
import random
import argparse
import logging
from typing import List

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')

ADB_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"

def run_adb(cmd: str) -> str:
    """Run an ADB shell command."""
    full_cmd = f'"{ADB_PATH}" shell {cmd}'
    try:
        result = subprocess.check_output(full_cmd, shell=True, text=True)
        return result.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"ADB command failed: {e}")
        return ""

def tap(x: int, y: int):
    """Tap at specific coordinates."""
    logging.info(f"Tapping ({x}, {y})")
    run_adb(f"input tap {x} {y}")

def type_text(text: str):
    """Type text simulating a human keyboard."""
    logging.info(f"Typing: {text}")
    # Replace spaces with %s for ADB input text
    encoded_text = text.replace(" ", "%s")
    run_adb(f"input text '{encoded_text}'")

def press_enter():
    """Press the Enter/Search key."""
    logging.info("Pressing ENTER")
    run_adb("input keyevent 66")

def go_back():
    """Press the Back button."""
    logging.info("Pressing BACK")
    run_adb("input keyevent 4")

def swipe_up(duration_ms=1000):
    """Swipe up to scroll down the page."""
    logging.info("Swiping up...")
    run_adb(f"input swipe 500 1500 500 300 {duration_ms}")

def human_delay(min_sec=1.0, max_sec=2.5):
    """Sleep for a random amount of time to simulate a human."""
    sleep_time = random.uniform(min_sec, max_sec)
    time.sleep(sleep_time)

def automate_search(queries: List[str], scrolls_per_query: int):
    logging.info(f"Starting automation for {len(queries)} queries.")
    
    # NOTE: You will need to replace these coordinates with the exact X,Y of the JustDial Search Bar!
    # For a typical 1080x1920 BlueStacks emulator, the search bar is often near the top (e.g., 500, 200).
    SEARCH_BAR_X = 540
    SEARCH_BAR_Y = 85
    
    # Sometimes there is a clear button in the search bar
    CLEAR_BTN_X = 950
    CLEAR_BTN_Y = 85
    
    for i, query in enumerate(queries):
        logging.info(f"=== Starting Query {i+1}/{len(queries)}: {query} ===")
        
        # 1. Tap Search Bar
        tap(SEARCH_BAR_X, SEARCH_BAR_Y)
        human_delay(0.5, 1.0)
        
        # 2. Type Query
        type_text(query)
        human_delay(0.5, 1.0)
        
        # 3. Press Enter (Search)
        press_enter()
        
        # 4. Wait for results to load
        logging.info("Waiting 5 seconds for results to load...")
        time.sleep(5)
        
        # 5. Scroll down N times
        for s in range(scrolls_per_query):
            logging.info(f"Scroll {s+1}/{scrolls_per_query} for '{query}'")
            swipe_up(duration_ms=random.randint(800, 1500))
            human_delay(1.5, 3.0)
            
        # 6. Go back to main screen
        go_back()
        human_delay(1.0, 2.0)
        
        # Clear the previous search
        tap(SEARCH_BAR_X, SEARCH_BAR_Y)
        human_delay(0.5, 1.0)
        tap(CLEAR_BTN_X, CLEAR_BTN_Y)
        human_delay(0.5, 1.0)
        
        logging.info(f"Finished query: {query}. Taking a breather before the next one.")
        human_delay(4.0, 7.0)
        
    logging.info("Automation Complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ADB Automator for JustDial")
    parser.add_argument("--queries", type=str, nargs="+", required=True, help="List of queries to search")
    parser.add_argument("--scrolls", type=int, default=10, help="Number of times to scroll down per query")
    args = parser.parse_args()
    
    automate_search(args.queries, args.scrolls)
