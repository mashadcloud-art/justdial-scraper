"""
Scraper module business logic: engine dispatch, ADB device/proxy helpers,
listing ingestion, and shared in-process scrape state.
"""
import os
import sys
import subprocess
import threading
import json
from typing import Optional

from config import settings

# ── Shared in-process state ──────────────────────────────────────────────────
scraping_in_progress = False
scraping_started_at = None  # Track when scraping started
adb_search_in_progress = False
ingest_lock = threading.Lock()
_scroll_process = None

smart_scrape_state = {
    "active": False,
    "compile_file": "",
    "district": "",
    "category": ""
}

ERROR_LOG_PATH = os.path.join(settings.DATA_FOLDER, "upload_error_log.txt")
UPLOAD_DIR = os.path.join(settings.DATA_FOLDER, "uploaded_images")
os.makedirs(settings.DATA_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_current_user(authorization: Optional[str]) -> Optional[dict]:
    """Decode the (unverified) JWT bearer token to scope requests by user_id."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    if not token or token == "null" or token == "undefined":
        return None
    try:
        import base64
        payload_segment = token.split(".")[1]
        padded = payload_segment + "=" * (4 - len(payload_segment) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(decoded_bytes.decode("utf-8"))
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email")
        }
    except Exception:
        return None


# ── Category/cuisine helpers for upload-listing ──────────────────────────────
CUISINE_KEYWORDS = [
    "South Indian", "North Indian", "Punjabi", "Chinese", "Continental",
    "Mughlai", "Bengali", "Gujarati", "Rajasthani", "Kerala", "Udupi",
    "Multicuisine", "Fast Food", "Barbeque", "Buffet", "Sea Food", "Seafood",
    "Veg", "Non Veg", "Street Food", "Desserts", "Italian", "Thai", "Mexican",
    "Pure Veg", "Tandoor", "Biryani", "Barbecue", "Pizza", "Bakery",
    "Ice Cream", "Juice", "Cafe", "Coffee", "Tea Stall", "Dhaba",
    "Bar", "Lounge", "Fine Dining", "Family Restaurant", "Vegetarian",
]


def looks_like_cuisine_tags(category: str) -> bool:
    if not category:
        return False
    cat_lower = category.lower()
    return any(kw.lower() in cat_lower for kw in CUISINE_KEYWORDS)


def process_category_subcategory(raw_category: str):
    if not raw_category:
        return "Restaurants", None

    if ">" in raw_category:
        parts = raw_category.split(">", 1)
        return parts[0].strip(), parts[1].strip()

    if looks_like_cuisine_tags(raw_category):
        return "Restaurants", raw_category

    return raw_category, None


# ── ADB helpers ───────────────────────────────────────────────────────────────
def get_adb_path():
    if os.name == "nt":
        bluestacks_adb = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
        if os.path.exists(bluestacks_adb):
            return bluestacks_adb
        scrcpy_adb = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scratch", "scrcpy", "scrcpy-win64-v4.0", "adb.exe"))
        if os.path.exists(scrcpy_adb):
            return scrcpy_adb
        return os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    return "adb"


def get_adb_devices(adb_path):
    try:
        if os.name != "nt":
            # On remote Linux server, connect to desktop emulator over Tailscale VPN
            try:
                subprocess.run(f'"{adb_path}" connect 100.103.62.50:5555', shell=True, timeout=1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        else:
            # On Windows local machine, connect to local BlueStacks instance
            # ONLY connect if we are NOT using the BlueStacks HD-Adb.exe
            if "HD-Adb.exe" not in adb_path:
                try:
                    subprocess.run(f'"{adb_path}" connect 127.0.0.1:5555', shell=True, timeout=5)
                except Exception:
                    pass
        out = subprocess.check_output(f'"{adb_path}" devices', shell=True, text=True)
        devices = []
        for line in out.strip().splitlines()[1:]:
            if line.strip() and "device" in line and "devices" not in line:
                devices.append(line.split()[0])
        return devices
    except Exception:
        return []


def get_local_ip():
    if os.name != "nt":
        try:
            out = subprocess.check_output("ip -o -4 addr show dev tailscale0", shell=True, text=True)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    ip = parts[3].split('/')[0]
                    if ip.startswith("100."):
                        return ip
        except Exception:
            pass
        return "129.151.146.44"
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def clear_stop_flag():
    flag_path = os.path.join(settings.DATA_FOLDER, "scrape_stop.flag")
    if os.path.exists(flag_path):
        try:
            os.remove(flag_path)
        except Exception:
            pass


SUBCATEGORIES_MAP = {
    "Home Services": ["Plumbers", "Electricians", "Carpenters", "Painters", "Cleaners"],
    "Restaurants": ["Fast Food", "Fine Dining", "Cafes", "Bakeries", "Chinese"],
    "Hospitals": ["Multi-Specialty", "Dental", "Eye Care", "Orthopedic", "Pediatric"],
    "Hotels": ["Budget", "3 Star", "4 Star", "5 Star", "Resorts"],
    "Education": ["Schools", "Colleges", "Coaching", "Play Schools", "Music Classes"],
    "Real Estate": ["Agents", "Builders", "PG / Hostels", "Rentals"],
    "Automobile": ["Car Dealers", "Bike Dealers", "Service Centres", "Spare Parts"],
    "Beauty & Spa": ["Salons", "Spas", "Nail Art", "Tattoo"],
    "Doctors": ["General Physician", "Cardiologist", "Dermatologist", "Gynaecologist"],
    "Travel": ["Travel Agents", "Cab Services", "Tour Operators", "Airlines"],
    "Home Decor": ["Furnitures", "Furnishing", "Lamps-Lighting", "Kitchen-Dining", "Interior-Designers"]
}
