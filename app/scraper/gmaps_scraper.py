"""
Google Maps ADB Scraper — New standalone module.
Does NOT modify or depend on any existing scraper code.

Two-stage extraction:
  Stage 1: List view XML  → extract business names + tap coordinates
  Stage 2: Detail view XML → extract full details (phone, address, hours, website, rating, coords)

Works with any Android emulator/device via ADB.
"""

import os
import subprocess
import time
import xml.etree.ElementTree as ET
import json
import re
from typing import List, Dict, Optional

try:
    from app.scraper.logger import log
except ImportError:
    def log(msg: str, ok: bool = True):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")


# ==========================================
# ADB CONFIGURATION
# ==========================================
def _detect_gmaps_adb():
    if os.name == "nt":
        bluestacks_adb = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
        if os.path.exists(bluestacks_adb):
            adb_path = bluestacks_adb
            adb_device = "emulator-5554"
            try:
                out = subprocess.check_output(f'"{adb_path}" devices', shell=True, text=True)
                for line in out.strip().splitlines()[1:]:
                    if line.strip() and "device" in line and "devices" not in line:
                        adb_device = line.split()[0]
                        break
            except Exception:
                pass
            return adb_path, adb_device
        else:
            return os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"), "127.0.0.1:5555"
    else:
        return "adb", ""

ADB_PATH, ADB_DEVICE = _detect_gmaps_adb()


def _run(cmd: str, shell_prefix: bool = True) -> str:
    """Run an ADB command and return output."""
    device_flag = f"-s {ADB_DEVICE}" if ADB_DEVICE else ""
    if shell_prefix:
        full = f'"{ADB_PATH}" {device_flag} shell {cmd}'
    else:
        full = f'"{ADB_PATH}" {device_flag} {cmd}'
    try:
        result = subprocess.check_output(full, shell=True, text=True,
                                          stderr=subprocess.DEVNULL, timeout=30)
        return result.strip()
    except Exception:
        return ""


def _pull(remote: str, local: str) -> bool:
    """Pull a file from device to local path."""
    device_flag = f"-s {ADB_DEVICE}" if ADB_DEVICE else ""
    try:
        subprocess.check_output(
            f'"{ADB_PATH}" {device_flag} pull {remote} "{local}"',
            shell=True, stderr=subprocess.DEVNULL, timeout=15
        )
        return os.path.exists(local)
    except Exception:
        return False


def _tap(x: int, y: int):
    _run(f"input tap {x} {y}")
    time.sleep(1.5)


def _back():
    _run("input keyevent 4")
    time.sleep(2)


def _dump_xml(path: str = "/sdcard/gmaps_view.xml") -> Optional[str]:
    """Dump UIAutomator XML and pull it locally."""
    _run(f"uiautomator dump {path}")
    time.sleep(1.5)
    local = os.path.join(os.path.dirname(__file__), "_gmaps_dump.xml")
    if _pull(path, local):
        with open(local, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return None


# ==========================================
# XML PARSING HELPERS
# ==========================================
def _parse_bounds(bounds_str: str) -> Dict:
    """Parse '[x1,y1][x2,y2]' into center x,y."""
    try:
        nums = re.findall(r"\d+", bounds_str)
        if len(nums) == 4:
            x1, y1, x2, y2 = map(int, nums)
            return {"cx": (x1 + x2) // 2, "cy": (y1 + y2) // 2,
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2}
    except Exception:
        pass
    return {}


def _get_all_nodes(xml_str: str) -> List[Dict]:
    """Flatten all XML nodes into a list with text + bounds."""
    nodes = []
    try:
        root = ET.fromstring(xml_str)
        for node in root.iter("node"):
            text = (node.attrib.get("text") or "").strip()
            content_desc = (node.attrib.get("content-desc") or "").strip()
            bounds = node.attrib.get("bounds", "")
            resource_id = node.attrib.get("resource-id", "")
            label = text or content_desc
            if label:
                nodes.append({
                    "text": label,
                    "bounds": bounds,
                    "coords": _parse_bounds(bounds),
                    "resource_id": resource_id,
                })
    except Exception as e:
        log(f"XML parse error: {e}", ok=False)
    return nodes


def _extract_list_items(xml_str: str) -> List[Dict]:
    """
    Stage 1: Extract business names + tap coords from list view XML.
    Google Maps list items are inside RecyclerView/ListView containers
    and have content-desc with business name + rating pattern.
    """
    items = []
    seen = set()

    # UI elements to always skip
    SKIP_EXACT = {
        "Search", "Back", "Navigate", "Directions", "More options",
        "Layers", "Recenter", "Saved", "Updates", "Contribute",
        "Explore", "Go", "You", "Share", "Save", "Send to phone",
        "Website", "Call", "Directions", "Open", "Closed",
        "Signed in as Owner", "Sign in", "Settings", "Help",
        "Feedback", "Menu", "Filter", "Sort", "List view", "Map view",
        "Charging", "Charged", "Battery", "Wi-Fi", "Bluetooth",
    }
    SKIP_CONTAINS = [
        "·", " mi", " km", " ft", "stars", "reviews",
        "Open now", "Closes soon", "Closed", "Opens at",
        "http", "www.", "google", "Loading", "Search here",
        "More results",
    ]

    try:
        root = ET.fromstring(xml_str)
        for node in root.iter("node"):
            clickable = node.attrib.get("clickable") == "true"
            if not clickable:
                continue

            text = (node.attrib.get("text") or "").strip()
            content_desc = (node.attrib.get("content-desc") or "").strip()
            bounds = node.attrib.get("bounds", "")
            rid = node.attrib.get("resource-id", "")

            # Prefer content-desc for Google Maps (it often has "Name, Rating, Category")
            label = content_desc if len(content_desc) > len(text) else text
            if not label:
                continue

            # Skip exact matches
            if label in SKIP_EXACT:
                continue

            # Skip if contains noise patterns
            if any(k.lower() in label.lower() for k in SKIP_CONTAINS):
                continue

            # Skip very short or very long strings
            if len(label) < 4 or len(label) > 200:
                continue

            # Skip if it looks like a UI button (single word common actions)
            if label.lower() in ["ok", "cancel", "close", "done", "next", "back",
                                   "yes", "no", "allow", "deny", "accept", "skip"]:
                continue

            # Skip strings that are mostly numbers/symbols (not business names)
            alpha_ratio = sum(c.isalpha() for c in label) / max(len(label), 1)
            if alpha_ratio < 0.4:
                continue

            # Get bounds and validate size
            coords = _parse_bounds(bounds)
            if not coords:
                continue

            # Skip tiny elements (likely icons/buttons, not cards)
            width = coords.get("x2", 0) - coords.get("x1", 0)
            height = coords.get("y2", 0) - coords.get("y1", 0)
            if width < 200 or height < 40:
                continue

            # Use first line of content_desc as the business name
            # Google Maps content_desc format: "Name\nRating stars X reviews\nCategory\nAddress"
            name = label.split("\n")[0].strip()
            if not name or name in seen:
                continue

            seen.add(name)
            items.append({
                "name": name,
                "tap_x": coords["cx"],
                "tap_y": coords["cy"],
                "bounds": bounds,
                "full_desc": label,
            })
    except Exception as e:
        log(f"List extraction error: {e}", ok=False)

    return items


def _extract_detail(xml_str: str) -> Dict:
    """
    Stage 2: Extract full business details from detail view XML.
    Parses phone, address, website, hours, rating, reviews, coordinates.
    """
    result = {
        "name": "", "address": "", "phone": "", "website": "",
        "rating": "", "reviews": "", "hours": "", "category": "",
        "latitude": "", "longitude": "",
    }

    nodes = _get_all_nodes(xml_str)
    texts = [n["text"] for n in nodes]

    # Patterns
    phone_re = re.compile(r"(\+?[\d\s\-\(\)]{7,20})")
    rating_re = re.compile(r"^(\d\.\d)$")
    reviews_re = re.compile(r"^[\(]?([\d,]+)\s*review", re.IGNORECASE)
    hours_re = re.compile(r"(Open|Closed|Opens|Closes).+", re.IGNORECASE)
    website_re = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
    coord_re = re.compile(r"geo:([\-\d.]+),([\-\d.]+)", re.IGNORECASE)

    for text in texts:
        # Name — usually the first large text at top
        if not result["name"] and len(text) > 3 and len(text) < 80:
            if not any(c.isdigit() for c in text[:3]):
                result["name"] = text

        # Phone
        if not result["phone"] and phone_re.match(text.strip()):
            digits = re.sub(r"\D", "", text)
            if 7 <= len(digits) <= 15:
                result["phone"] = text.strip()

        # Rating
        if not result["rating"] and rating_re.match(text.strip()):
            result["rating"] = text.strip()

        # Reviews
        if not result["reviews"]:
            m = reviews_re.search(text)
            if m:
                result["reviews"] = m.group(1).replace(",", "")

        # Hours
        if not result["hours"] and hours_re.match(text.strip()):
            result["hours"] = text.strip()

        # Website
        if not result["website"] and website_re.search(text):
            result["website"] = text.strip()

        # Address — lines with numbers + street-like words
        if not result["address"] and re.search(
                r"\d+.*\b(St|Rd|Ave|Blvd|Lane|Dr|Al |district|area|near)\b",
                text, re.IGNORECASE):
            result["address"] = text.strip()

    # Try to get coordinates from dumpsys
    dumpsys = _run("dumpsys activity | grep -i geo:")
    coord_match = coord_re.search(dumpsys)
    if coord_match:
        result["latitude"] = coord_match.group(1)
        result["longitude"] = coord_match.group(2)

    return result


# ==========================================
# MAIN SCRAPER
# ==========================================
def scrape_gmaps(query: str, max_results: int = 20,
                 scroll_count: int = 5) -> Dict:
    """
    Main entry point.
    Opens Google Maps silently, extracts list + detail pages.

    Args:
        query: e.g. "Hospitals in Abu Dhabi"
        max_results: max businesses to scrape
        scroll_count: how many times to scroll the list

    Returns:
        {"query": ..., "results": [...]}
    """
    log(f"🗺️ Google Maps Scraper starting: '{query}'")
    output = {"query": query, "results": []}

    # ---- Stage 0: Open Google Maps silently ----
    encoded_query = query.replace(" ", "+")
    intent = (f"am start -a android.intent.action.VIEW "
              f"-d \"geo:0,0?q={encoded_query}\" "
              f"-n com.google.android.apps.maps/com.google.android.maps.MapsActivity")

    log(f"📍 Launching Maps: {intent}")
    _run(intent)
    time.sleep(6)  # BlueStacks needs more time to load Maps

    # Switch to List view (tap the list view button if available)
    log("📋 Switching to List view...")
    # Try tapping "List view" button - common in Google Maps search results
    _run("input tap 900 120")  # top-right area where list/map toggle usually is
    time.sleep(2)
    # Also try swiping up on bottom sheet to expand results list
    _run("input swipe 540 900 540 300 600")
    time.sleep(3)

    # ---- Stage 1: Extract list items ----
    all_items = []
    seen_names = set()

    for scroll_idx in range(scroll_count + 1):
        log(f"📋 Stage 1 — Dumping list view (scroll {scroll_idx}/{scroll_count})...")
        xml_str = _dump_xml("/sdcard/gmaps_list.xml")

        if not xml_str:
            log("⚠️ Could not get XML dump", ok=False)
            break

        items = _extract_list_items(xml_str)
        new_items = [i for i in items if i["name"] not in seen_names]
        for item in new_items:
            seen_names.add(item["name"])
            all_items.append(item)
            log(f"  Found: {item['name']}")

        if len(all_items) >= max_results:
            break

        if scroll_idx < scroll_count:
            # Scroll down to load more results
            _run("input swipe 540 1200 540 400 800")
            time.sleep(2)

    log(f"✅ Stage 1 complete. Found {len(all_items)} businesses.")
    all_items = all_items[:max_results]

    # ---- Stage 2: Visit each detail page ----
    for idx, item in enumerate(all_items):
        log(f"\n📄 Stage 2 [{idx+1}/{len(all_items)}] — Getting details: {item['name']}")

        # Tap the list item to open detail page
        _tap(item["tap_x"], item["tap_y"])
        time.sleep(3)  # Wait for detail page to load

        # Dump detail page XML
        xml_str = _dump_xml("/sdcard/gmaps_detail.xml")
        if not xml_str:
            log(f"  ⚠️ No XML for {item['name']}", ok=False)
            _back()
            continue

        # Extract full details
        details = _extract_detail(xml_str)

        # Use list item name if detail extraction missed it
        if not details["name"]:
            details["name"] = item["name"]

        log(f"  📝 Name    : {details['name']}")
        log(f"  📞 Phone   : {details['phone'] or 'N/A'}")
        log(f"  📍 Address : {details['address'] or 'N/A'}")
        log(f"  🌐 Website : {details['website'] or 'N/A'}")
        log(f"  ⭐ Rating  : {details['rating'] or 'N/A'}")
        log(f"  🕐 Hours   : {details['hours'] or 'N/A'}")
        log(f"  🌍 Coords  : {details['latitude']},{details['longitude']}")

        output["results"].append(details)

        # Go back to list
        _back()
        time.sleep(1.5)

    log(f"\n🏁 Google Maps scrape complete. {len(output['results'])} results.")
    return output


def save_results(data: Dict, output_path: str = None) -> str:
    """Save results to JSON file."""
    if not output_path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        query_slug = re.sub(r"[^a-z0-9]", "_", data["query"].lower())[:30]
        output_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "data",
            f"gmaps_{query_slug}_{ts}.json"
        )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"💾 Saved to: {output_path}")
    return output_path


def upload_to_db(data: Dict, district: str = "") -> int:
    """
    Upload scraped Google Maps results into the existing database.
    Uses the same upload endpoint as the rest of the app.
    """
    import requests as req
    API_URL = "http://localhost:8000/api/v1/upload-restaurant"
    success = 0

    for r in data.get("results", []):
        if not r.get("name"):
            continue

        district_val = district or _extract_district(r.get("address", ""),
                                                      data["query"])
        payload = {
            "name": r["name"],
            "phone": r.get("phone", ""),
            "address": r.get("address", ""),
            "source_url": r.get("website", f"https://maps.google.com/?q={r['name'].replace(' ','+')}"),
            "category": r.get("category", ""),
            "opening_hours": r.get("hours", ""),
            "district": district_val,
            "latitude": r.get("latitude", ""),
            "longitude": r.get("longitude", ""),
        }
        try:
            resp = req.post(API_URL, data=payload, timeout=10)
            if resp.status_code in (200, 201):
                success += 1
                log(f"  ✅ Uploaded: {r['name']}")
            else:
                log(f"  ❌ Failed: {r['name']} — {resp.status_code}", ok=False)
        except Exception as e:
            log(f"  ❌ Upload error: {e}", ok=False)

    log(f"📤 Uploaded {success}/{len(data['results'])} to database.")
    return success


def _extract_district(address: str, query: str) -> str:
    """Try to extract district/city from address or query."""
    for part in [address, query]:
        m = re.search(r"\bin\s+([A-Z][a-zA-Z\s]+)", part)
        if m:
            return m.group(1).strip()
    return ""


# ==========================================
# CLI ENTRY POINT
# ==========================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Google Maps ADB Scraper")
    parser.add_argument("query", help='Search query e.g. "Hospitals in Abu Dhabi"')
    parser.add_argument("--max", type=int, default=20, help="Max results")
    parser.add_argument("--scrolls", type=int, default=5, help="Scroll count")
    parser.add_argument("--upload", action="store_true", help="Upload to database")
    parser.add_argument("--district", default="", help="District name for DB upload")
    args = parser.parse_args()

    results = scrape_gmaps(args.query, max_results=args.max,
                           scroll_count=args.scrolls)
    save_results(results)

    if args.upload:
        upload_to_db(results, district=args.district)
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))
