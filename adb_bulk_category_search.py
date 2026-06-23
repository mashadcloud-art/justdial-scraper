import time
import random
import argparse
import sys
import os

# Put project path in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import app.scraper.adb_location_search as adb_location_search
from app.scraper.adb_location_search import run_adb, tap, type_text, press_enter, go_back, swipe_up, human_delay, log

# Default categories list provided by the user
DEFAULT_CATEGORIES = [
    "Car Rental",
    "Costumes On Rent",
    "Mini Bus On Rent",
    "Furnitures On Rent",
    "Blazers On Rent",
    "Bridal Wear On Rent",
    "Bungalows On Rent",
    "Bus On Rent",
    "Computers On Rent",
    "Cranes On Rent",
    "DJ Equipments On Rent",
    "Farm House On Rent"
]

def clear_search_input():
    """Taps the clear 'X' button in the search input box (usually near X=920, Y=150) or sends backspaces."""
    log("Clearing search input box...")
    # Try tapping the clear button first
    tap(850, 150)
    human_delay(0.5, 0.8)
    # Send a few backspaces just in case
    for _ in range(25):
        run_adb(f"{adb_location_search.get_input_cmd()} keyevent 67")

def get_visible_companies() -> list:
    """Dumps the screen layout using UIAutomator and extracts visible company names."""
    try:
        run_adb("uiautomator dump /sdcard/scroll_dump.xml > /dev/null 2>&1")
        xml_content = run_adb("cat /sdcard/scroll_dump.xml")
        if not xml_content or "xml" not in xml_content:
            return []
        
        import xml.etree.ElementTree as ET
        # Strip XML declaration if present to avoid parsing errors
        if xml_content.startswith("<?xml"):
            end_decl = xml_content.find("?>")
            if end_decl != -1:
                xml_content = xml_content[end_decl + 2:]
        
        root = ET.fromstring(xml_content.strip())
        names = []
        for node in root.iter('node'):
            rid = node.get('resource-id', '')
            if 'comp_name' in rid:
                name_val = node.get('text', '').strip()
                if name_val:
                    names.append(name_val)
        return names
    except Exception as e:
        log(f"Error parsing visible companies: {e}", ok=False)
        return []

def automate_category_search(location: str, categories: list, scrolls: int = 15):
    """
    Loops through categories on the BlueStacks emulator. Searches for 'category in location'
    directly to ensure results are always from the target location without using fragile location headers.
    """
    print(f"Starting ADB Scraper for {len(categories)} categories in location: {location}")
    
    # Launch JustDial app
    print("Launching JustDial app...")
    if adb_location_search.ADB_DISPLAY is not None:
        run_adb(f"am start --display {adb_location_search.ADB_DISPLAY} -n com.justdial.search/.SplashScreenNewActivity")
    else:
        run_adb("monkey -p com.justdial.search -c android.intent.category.LAUNCHER 1")
    time.sleep(4.0)

    for i, category in enumerate(categories):
        search_query = f"{category} in {location}"
        print(f"\n==========================================")
        print(f"[{i+1}/{len(categories)}] Search Query: {search_query}")
        print(f"==========================================")

        try:
            # TODO: USER WILL PROVIDE THESE COORDINATES based on their Pointer Location overlay
            HOME_SEARCH_X, HOME_SEARCH_Y = 400, 170
            INPUT_BOX_X, INPUT_BOX_Y = 450, 150
            
            if i == 0:
                # FIRST RUN: Tap search bar on home page
                tap(HOME_SEARCH_X, HOME_SEARCH_Y)
                human_delay(1.5, 2.0)
                
                # Tap the category search input box
                tap(INPUT_BOX_X, INPUT_BOX_Y)
                human_delay(0.8, 1.2)
                
                # Type the full query (e.g. "Car Rental in Kasaragod")
                type_text(search_query)
                human_delay(1.0, 1.5)
                
                # Press enter to search
                press_enter()
                human_delay(4.0, 6.0) # Wait for search results to load
            else:
                # SUBSEQUENT RUNS:
                # 1. Press BACK once to return to search input screen
                go_back()
                human_delay(1.5, 2.0)

                # 2. Tap the search input box
                tap(INPUT_BOX_X, INPUT_BOX_Y)
                human_delay(0.8, 1.2)

                # 3. Clear the previous category text
                clear_search_input()
                human_delay(0.8, 1.2)

                # 4. Type the new query
                type_text(search_query)
                human_delay(1.0, 1.5)

                # 5. Press Enter to execute search
                press_enter()
                human_delay(4.0, 6.0) # Wait for search results to load
            
            # Smart scrolling: Scroll until no new company listings appear
            print(f"   Starting smart scrolling for '{search_query}'...")
            consecutive_no_change = 0
            last_companies = []
            max_scrolls = 40  # Maximum scroll safety limit
            
            for s in range(1, max_scrolls + 1):
                swipe_up(duration_ms=random.randint(600, 1000))
                human_delay(1.5, 2.2) # Wait for page load
                
                # Check current visible companies
                current_companies = get_visible_companies()
                
                if current_companies and current_companies == last_companies:
                    consecutive_no_change += 1
                    print(f"   Scroll {s}: No new results loaded (consecutive: {consecutive_no_change})")
                else:
                    consecutive_no_change = 0
                    if current_companies:
                        last_companies = current_companies
                        print(f"   Scroll {s}: Loaded listings: {current_companies[-2:]}") # Print last two names
                
                if consecutive_no_change >= 2:
                    print("   Reached the end of the results (no change in visible companies).")
                    break

        except Exception as e:
            print(f"Error during search for {category}: {e}")
            # Try to return to a safe home state by hitting back a few times
            go_back()
            go_back()
            time.sleep(2)
            
    print("\nBulk Category search automation complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk Category ADB Automator for JustDial")
    parser.add_argument("--location", default="Kutch", help="Location (PIN/Town) to search in")
    parser.add_argument("--scrolls", type=int, default=15, help="Number of scrolls per category")
    parser.add_argument("--display", type=int, default=None, help="ADB display ID (use 3 for DeX)")
    args = parser.parse_args()
    
    if args.display is not None:
        adb_location_search.ADB_DISPLAY = args.display
        
    automate_category_search(args.location, DEFAULT_CATEGORIES, args.scrolls)
