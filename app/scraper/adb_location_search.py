import os
import subprocess
import time
import random
import argparse
import logging
from typing import List
import xml.etree.ElementTree as ET

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

# BlueStacks common ADB ports to try when reconnecting
BLUESTACKS_PORTS = [5555, 5556, 5557, 5558, 5585, 5554]

def _get_adb_exe():
    """Return the path to the ADB executable."""
    if os.name == "nt":
        bluestacks_adb = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
        if os.path.exists(bluestacks_adb):
            return bluestacks_adb
        return os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    return "adb"

ADB_PATH = _get_adb_exe()

def _detect_connected_device() -> str:
    """Dynamically detect the first connected ADB device. Returns '-s <device>' or ''."""
    try:
        out = subprocess.check_output(f'"{ADB_PATH}" devices', shell=True, text=True, stderr=subprocess.DEVNULL)
        devices = []
        for line in out.strip().splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        if devices:
            return f"-s {devices[0]}"
    except Exception:
        pass
    return ""

def ensure_device_connected() -> bool:
    """Try to connect BlueStacks via ADB if no device is detected. Returns True if connected."""
    target = _detect_connected_device()
    if target:
        log(f"ADB device already connected: {target.replace('-s ', '')}")
        return True

    log("No ADB device found. Attempting to connect to BlueStacks...")
    for port in BLUESTACKS_PORTS:
        try:
            out = subprocess.check_output(
                f'"{ADB_PATH}" connect 127.0.0.1:{port}',
                shell=True, text=True, stderr=subprocess.DEVNULL
            )
            if "connected" in out.lower() and "unable" not in out.lower():
                log(f"Connected to BlueStacks on 127.0.0.1:{port}")
                time.sleep(1.5)
                return True
        except Exception:
            pass

    log("Could not connect to BlueStacks ADB. Is BlueStacks running with ADB enabled?", ok=False)
    return False

# ADB_TARGET is resolved dynamically at runtime per call
ADB_TARGET = ""
ADB_DISPLAY = None


def run_adb(cmd: str) -> str:
    """Run an ADB shell command using dynamically detected device."""
    device_target = _detect_connected_device()
    if device_target:
        full_cmd = f'"{ADB_PATH}" {device_target} shell {cmd}'
    else:
        full_cmd = f'"{ADB_PATH}" shell {cmd}'

    try:
        result = subprocess.check_output(full_cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        return result.strip()
    except subprocess.CalledProcessError as e:
        log(f"ADB command failed: {e}", ok=False)
        return ""

def run_adb_pull(remote_path: str, local_path: str) -> bool:
    """Pull a file from the device to local disk (top-level adb pull, not shell)."""
    device_target = _detect_connected_device()
    if device_target:
        full_cmd = f'"{ADB_PATH}" {device_target} pull "{remote_path}" "{local_path}"'
    else:
        full_cmd = f'"{ADB_PATH}" pull "{remote_path}" "{local_path}"'
    try:
        subprocess.check_output(full_cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        return os.path.exists(local_path)
    except subprocess.CalledProcessError:
        return False


def get_input_cmd():
    if ADB_DISPLAY is not None:
        return f"input -d {ADB_DISPLAY}"
    return "input"


def tap(x: int, y: int):
    """Tap at specific coordinates."""
    log(f"Tapping ({x}, {y})")
    run_adb(f"{get_input_cmd()} tap {x} {y}")

def type_text(text: str):
    """Type text simulating a human keyboard."""
    log(f"Typing: {text}")
    safe_text = text.replace("&", "and")
    encoded_text = safe_text.replace(" ", "%s")
    run_adb(f"{get_input_cmd()} text '{encoded_text}'")


def press_enter():
    """Press the Enter/Search key."""
    log("Pressing ENTER")
    run_adb(f"{get_input_cmd()} keyevent 66")

def go_back():
    """Press the Back button."""
    log("Pressing BACK")
    run_adb(f"{get_input_cmd()} keyevent 4")

def tap_home_nav():
    """Tap the Home tab in the JustDial bottom navigation bar.
    This navigates to the home screen WITHOUT killing the app,
    so the selected city is preserved between searches.
    """
    log("Tapping JustDial Home nav button...")
    # JustDial bottom nav: Home tab is leftmost, approximately at (75, 1563)
    # on a 900x1600 screen layout
    run_adb(f"{get_input_cmd()} tap 75 1563")

def swipe_up(duration_ms=1000):
    """Swipe up to scroll down the page."""
    log("Swiping up...")
    run_adb(f"{get_input_cmd()} swipe 500 1500 500 300 {duration_ms}")

def human_delay(min_sec=1.0, max_sec=2.5):
    """Sleep for a random amount of time to simulate a human."""
    sleep_time = random.uniform(min_sec, max_sec)
    time.sleep(sleep_time)

def check_stop_flag() -> bool:
    """Check if the user requested to stop the scraper."""
    import os
    paths = [
        "data/scrape_stop.flag",
        "../../data/scrape_stop.flag",
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "scrape_stop.flag")
    ]
    for p in paths:
        if os.path.exists(p):
            return True
    return False

def check_current_city() -> str:
    """Get the currently selected city from the search screen."""
    temp_xml_path = "/sdcard/temp_search_screen.xml"
    run_adb(f"uiautomator dump {temp_xml_path}")

    local_xml = os.path.join(os.path.dirname(__file__), "..", "..", "data", "temp_search_screen.xml")
    os.makedirs(os.path.dirname(local_xml), exist_ok=True)

    pulled = run_adb_pull(temp_xml_path, local_xml)

    if not pulled:
        log("Failed to read search screen layout XML.")
        return ""

    try:
        tree = ET.parse(local_xml)
        root = tree.getroot()
        for node in root.iter():
            rid = node.attrib.get("resource-id", "").strip()
            if "jd_detected_area_view" in rid:
                current_city = node.attrib.get("text", "").strip()
                log(f"Current selected city in app: '{current_city}'")
                return current_city
    except Exception as e:
        log(f"Error parsing search screen XML: {e}")

    return ""

def select_city_on_screen(target_city: str) -> bool:
    """Select the target city on the screen dynamically."""
    log(f"Changing global city to: {target_city}")
    # 1. Tap city selector (X=450, Y=62) on the search screen
    log("Tapping city selector...")
    tap(450, 62)
    human_delay(2.5, 3.5)

    # 2. Type target city name
    log(f"Typing '{target_city}'...")
    type_text(target_city)
    human_delay(3.5, 4.5)

    # 3. Dump suggestion XML to find the suggestion item
    temp_xml_path = "/sdcard/temp_suggestions.xml"
    run_adb(f"uiautomator dump {temp_xml_path}")

    local_xml = os.path.join(os.path.dirname(__file__), "..", "..", "data", "temp_suggestions.xml")
    os.makedirs(os.path.dirname(local_xml), exist_ok=True)

    pulled = run_adb_pull(temp_xml_path, local_xml)

    if not pulled:
        log("Failed to dump suggestions XML, tapping fallback coordinates.", ok=False)
        tap(450, 509)
        human_delay(4.0, 5.0)
        return False

    try:
        tree = ET.parse(local_xml)
        root = tree.getroot()
        parent_map = {c: p for p in root.iter() for c in p}

        target_node = None
        for node in root.iter():
            text = node.attrib.get("text", "").strip()
            rid = node.attrib.get("resource-id", "").strip()
            if "tvAreaView" in rid and target_city.lower() in text.lower():
                target_node = node
                log(f"Found matching city suggestion: '{text}'")
                break

        # Fallback to first tvAreaView
        if target_node is None:
            for node in root.iter():
                rid = node.attrib.get("resource-id", "").strip()
                if "tvAreaView" in rid:
                    target_node = node
                    log(f"Fallback to first suggestion: '{node.attrib.get('text')}'")
                    break

        if target_node is not None:
            clickable_ancestor = None
            curr = target_node
            while curr is not None:
                if curr.attrib.get("clickable") == "true":
                    clickable_ancestor = curr
                    break
                curr = parent_map.get(curr)

            bounds_node = clickable_ancestor if clickable_ancestor is not None else target_node
            bounds_str = bounds_node.attrib.get("bounds")
            coords = bounds_str.replace("][", ",").replace("[", "").replace("]", "").split(",")
            x1, y1, x2, y2 = map(int, coords)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            log(f"Tapping suggestion at ({cx}, {cy})")
            tap(cx, cy)
        else:
            log("No suggestions found in XML, tapping fallback coordinates.", ok=False)
            tap(450, 509)
    except Exception as e:
        log(f"Error parsing suggestions XML: {e}, tapping fallback coordinates.", ok=False)
        tap(450, 509)

    human_delay(4.0, 5.0)
    return True


def check_and_dismiss_refinement(category: str, max_retries: int = 3) -> bool:
    """
    Check if stuck on a subcategory/price refinement screen
    (e.g. Fast Food > Inexpensive / Moderate / Expensive).
    Taps the category item (e.g. 'Fast Food') at the top of the list
    to proceed to the actual business listings.
    Retries up to max_retries times.
    """
    REFINEMENT_KEYWORDS = {"inexpensive", "moderate", "expensive", "budget", "fine dining"}
    SKIP_TEXTS = {
        "select location", "select category",
        "inexpensive", "moderate", "expensive", "budget", "fine dining",
        "home", "shop", "stocks", "pay", "news", "more"
    }

    for attempt in range(1, max_retries + 1):
        temp_xml_path = "/sdcard/temp_refinement_check.xml"
        run_adb(f"uiautomator dump {temp_xml_path}")

        local_xml = os.path.join(os.path.dirname(__file__), "..", "..", "data", "temp_refinement_check.xml")
        os.makedirs(os.path.dirname(local_xml), exist_ok=True)

        pulled = run_adb_pull(temp_xml_path, local_xml)
        if not pulled:
            log("Could not pull refinement XML, skipping check.", ok=False)
            return False

        try:
            tree = ET.parse(local_xml)
            root = tree.getroot()
            parent_map = {c: p for p in root.iter() for c in p}

            all_texts = {node.attrib.get("text", "").strip().lower() for node in root.iter()}

            # Not on a refinement screen — we're good
            if not any(kw in all_texts for kw in REFINEMENT_KEYWORDS):
                if attempt == 1:
                    log("No refinement screen detected.")
                else:
                    log("Refinement screen successfully dismissed.")
                return attempt > 1

            log(f"Refinement screen detected (attempt {attempt}/{max_retries}). Tapping '{category}'...")

            target_node = None

            # Priority 1: exact match with the category name (e.g. "Fast Food")
            for node in root.iter():
                if node.attrib.get("text", "").strip().lower() == category.lower():
                    target_node = node
                    log(f"Found exact match: '{node.attrib.get('text')}'")
                    break

            # Priority 2: first non-refinement non-nav TextView
            if target_node is None:
                for node in root.iter():
                    text = node.attrib.get("text", "").strip()
                    cls = node.attrib.get("class", "").strip()
                    if text and "TextView" in cls and text.lower() not in SKIP_TEXTS:
                        target_node = node
                        log(f"Fallback: tapping first valid item '{text}'")
                        break

            if target_node is None:
                log("No valid tap target found on refinement screen. Pressing BACK.", ok=False)
                go_back()
                human_delay(2.0, 3.0)
                continue

            # Walk up to closest clickable ancestor
            curr = target_node
            while curr is not None:
                if curr.attrib.get("clickable") == "true":
                    target_node = curr
                    break
                curr = parent_map.get(curr)

            bounds_str = target_node.attrib.get("bounds", "")
            if not bounds_str:
                log("Target node has no bounds. Pressing BACK.", ok=False)
                go_back()
                human_delay(2.0, 3.0)
                continue

            coords = bounds_str.replace("][", ",").replace("[", "").replace("]", "").split(",")
            x1, y1, x2, y2 = map(int, coords)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            log(f"Tapping '{target_node.attrib.get('text', '?')}' at ({cx}, {cy}) to dismiss refinement")
            tap(cx, cy)
            human_delay(3.5, 4.5)

        except Exception as e:
            log(f"Error dismissing refinement screen: {e}", ok=False)
            go_back()
            human_delay(2.0, 3.0)

    log("Could not dismiss refinement screen after all retries.", ok=False)
    return False


def automate_location_search(locations: List[str], category: str, scrolls: int, city: str = None):
    log(f"Starting targeted search for {len(locations)} locations.")

    # Ensure ADB is connected before starting any automation
    if not ensure_device_connected():
        log("Cannot start scrape: No ADB device available. Please open BlueStacks and enable ADB.", ok=False)
        return

    # =========================================================
    # STEP 1: Start the app ONCE — do NOT restart between pincodes
    # Restarting kills the city setting and reverts to Mumbai!
    # =========================================================
    log("Starting JustDial app (ONE TIME only)...")
    run_adb("am force-stop com.justdial.search")
    human_delay(1.0, 1.5)
    if ADB_DISPLAY is not None:
        run_adb(f"am start --display {ADB_DISPLAY} -n com.justdial.search/.SplashScreenNewActivity")
    else:
        run_adb("monkey -p com.justdial.search -c android.intent.category.LAUNCHER 1")
    human_delay(5.0, 6.0)  # Wait for home screen to fully load

    # =========================================================
    # STEP 2: Set city ONCE before entering the pincode loop
    # City stays set for the entire session as long as we don't
    # force-stop the app.
    # =========================================================
    if city:
        log(f"Setting city to '{city}' (this is done ONCE for all pincodes)...")
        tap(450, 170)  # Open search screen from home
        human_delay(2.5, 3.5)
        curr_city = check_current_city()
        if city.lower() not in curr_city.lower():
            log(f"City mismatch: app shows '{curr_city}', need '{city}'. Changing now...")
            select_city_on_screen(city)
            # select_city_on_screen navigates back to home after selecting
            human_delay(2.0, 3.0)
            log(f"City should now be set to '{city}' for all upcoming searches.")
        else:
            log(f"City '{city}' is already selected. No change needed.")
            go_back()  # Return to home screen
            human_delay(1.0, 1.5)

    # =========================================================
    # STEP 3: Loop through all pincodes WITHOUT restarting the app
    # We navigate via the bottom nav Home button — city is preserved!
    # =========================================================
    for i, loc in enumerate(locations):
        if check_stop_flag():
            log("🛑 Scraper stopped by user request. Exiting.", ok=False)
            return

        log(f"=== [Location {i+1}/{len(locations)}] Searching: {category} in {loc} ===")

        # Navigate to JustDial home screen via bottom nav Home button
        # This does NOT kill the app — city setting stays intact
        log("Tapping Home nav button to return to JustDial home...")
        tap_home_nav()
        human_delay(1.5, 2.5)

        # Open search screen from home
        tap(450, 170)
        human_delay(2.0, 2.5)

        # Focus the search input (it will be empty — fresh search from home)
        tap(450, 150)
        human_delay(0.8, 1.2)

        # Type the search query
        search_query = f"{category} in {loc}"
        type_text(search_query)
        human_delay(1.5, 2.0)

        # Press Enter to submit search
        if check_stop_flag():
            log("🛑 Scraper stopped by user request. Exiting.", ok=False)
            return
        press_enter()
        human_delay(5.0, 7.0)  # Wait for results / refinement screen to load

        # =====================================================
        # Handle refinement screen (Fast Food > Inexpensive etc.)
        # Taps "Fast Food" at the top to go to actual listings
        # =====================================================
        check_and_dismiss_refinement(category)

        # Scroll down to trigger API data capture
        for s in range(1, scrolls + 1):
            if check_stop_flag():
                log("🛑 Scraper stopped by user request. Exiting.", ok=False)
                return

            log(f"Scroll {s}/{scrolls} for '{search_query}'")
            swipe_up(duration_ms=random.randint(600, 1000))
            swipe_up(duration_ms=random.randint(600, 1000))
            human_delay(1.2, 2.0)

    log("Location-based search automation complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Targeted Location ADB Automator for JustDial")
    parser.add_argument("--locations", nargs="+", required=True, help="List of PIN codes or town names")
    parser.add_argument("--category", default="Restaurants", help="Category to search (default: Restaurants)")
    parser.add_argument("--scrolls", type=int, default=15, help="Number of scrolls per search")
    parser.add_argument("--display", type=int, default=None, help="ADB display ID (use 3 for DeX)")
    parser.add_argument("--city", default=None, help="Global city/district to set before searching")
    args = parser.parse_args()

    if args.display is not None:
        ADB_DISPLAY = args.display

    automate_location_search(args.locations, args.category, args.scrolls, city=args.city)
