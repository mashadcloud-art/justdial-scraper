import time
import random
import os
import subprocess
import sys

def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    try:
        print(f"[{timestamp}] {msg}")
    except UnicodeEncodeError:
        import sys
        encoding = sys.stdout.encoding or 'utf-8'
        safe_msg = msg.encode(encoding, errors='replace').decode(encoding)
        print(f"[{timestamp}] {safe_msg}")

ADB_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")

def run_adb(cmd):
    try:
        # Use specific device to avoid 'more than one device' error, and don't silence errors!
        full_cmd = f'"{ADB_PATH}" -s 127.0.0.1:5556 shell {cmd}'
        subprocess.run(full_cmd, shell=True, check=True)
    except Exception as e:
        log(f"ADB command failed: {e}")

def swipe_up(duration_ms=1000):
    run_adb(f"input swipe 500 1500 500 300 {duration_ms}")

def human_delay(min_sec=1.0, max_sec=2.5):
    time.sleep(random.uniform(min_sec, max_sec))

KASARAGOD_PINCODES = [
    "671121", "671122", "671123", "671124", "671312", "671313", "671314",
    "671315", "671316", "671321", "671322"
]

CATEGORIES = [
    "Hospitals",
    "Ayurvedic Hospitals",
    "Homeopathic Hospitals",
    "Dental Hospitals",
    "Eye Hospitals",
    "Maternity Hospitals",
    "Veterinary Hospitals",
    "Children Hospitals",
    "Cardiology Hospitals",
    "Neurology Hospitals",
    "Orthopaedic Hospitals"
]

def automate_deep_links():
    log("🚀 Starting ADB Deep-Link Scraper for Kasaragod Hospitals")
    
    # Ensure screen is awake and unlocked
    run_adb("input keyevent KEYCODE_WAKEUP")
    run_adb("input keyevent 82")
    human_delay(1, 2)
    
    # Force stop justdial to clear memory
    run_adb("am force-stop com.justdial.search")
    human_delay(2, 3)

    for category in CATEGORIES:
        for pin in KASARAGOD_PINCODES:
            search_query = f"{category} in {pin}"
            log(f"\n==========================================")
            log(f"📊 Search Query: {search_query}")
            log(f"==========================================")
            
            # Use intent deep-link to completely bypass the search bar and tapping!
            cat_url = category.replace(" ", "-")
            url = f"https://www.justdial.com/{pin}/{cat_url}"
            log(f"🔗 Deep-linking to: {url}")
            
            run_adb(f'am start -W -a android.intent.action.VIEW -d "{url}"')
            human_delay(5.0, 7.0) # Wait for JustDial to load the page

            # Scroll down to trigger the API calls (MITM will catch them)
            scrolls = 15
            for s in range(1, scrolls + 1):
                log(f"   Scroll {s}/{scrolls} for '{search_query}'...")
                swipe_up(duration_ms=random.randint(600, 1000))
                human_delay(1.2, 2.0)
                
    log("🏁 Finished scraping all pincodes and categories!")

if __name__ == "__main__":
    automate_deep_links()
