"""
JustDial Direct API Scraper
===========================
Calls the JustDial internal API (same endpoint as the Android app) directly,
bypassing all browser automation and Cloudflare blocks.

Extracts:
  - Full listing details (name, phone, address, rating, etc.)
  - dimages: Full-resolution JustDial CDN images (jdmagicbox.com)
  - Menu images (catalog images)
  - Saves directly to Supabase database

Usage:
  python jd_api_scraper.py --district Palakkad --category "Restaurants" --pages 5
"""
import argparse
import json
import os
import sys
import time
import re
import uuid
import base64
import jwt
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.database import SessionLocal
from app import models
from sqlalchemy.exc import IntegrityError
from app.api.pincodes import get_pincodes_for_district

# ─── JustDial API Config ──────────────────────────────────────────────────────
# Extracted from Android app traffic via MITM proxy
JD_API_BASE = "https://win.justdial.com/01march2019/searchziva.php"
SECRET_KEY = "2MQkzWVlwMx44uSC3KvWGk4nYiXQ3cMicyZQP7oc8y6KcflHR9zksp2eT1YHAGQL9EYr/Bdydfmr9jVNkRRwFg=="

# Rotates between the user's 69 different Webshare static residential proxy credentials
import random
def get_random_proxy():
    # Credentials format: wnjqhjor-IN-X:0clsqfyfo9wa where X is between 1 and 69
    num = random.randint(1, 69)
    proxy_str = f"http://wnjqhjor-IN-{num}:0clsqfyfo9wa@p.webshare.io:80/"
    return {
        "http": proxy_str,
        "https": proxy_str
    }

PROXIES = get_random_proxy()
# NOTE: Proxy disabled for search requests — Webshare IPs are from random Indian cities
# (Delhi/Bangalore) causing JustDial to return wrong city results.
# Use NO_PROXY for direct search, proxy only needed on Oracle Cloud server.
NO_PROXY = None

def generate_jd_bearer_token():
    """Generate signed JWT token mimicking JustDial app authentication."""
    nano_time = time.time_ns()
    random_uuid = str(uuid.uuid4())
    b64_uuid = base64.b64encode(random_uuid.encode('utf-8')).decode('utf-8')
    
    payload = {
        "iat": nano_time,
        "jti": b64_uuid,
        "iss": "justdial",
        "exp": nano_time,
        "source": "android"
    }
    
    headers = {
        "typ": "JWT"
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256", headers=headers)


# Image base URL
JD_IMAGE_BASE = "https://images.jdmagicbox.com"
JD_CONTENT_BASE = "https://content.jdmagicbox.com"

# Category slug mapping for JustDial search
CATEGORY_SLUGS = {
    "Restaurants": "Restaurants",
    "Hotels": "Hotels",
    "Hospitals": "Hospitals",
    "Clinics": "Clinics",
    "Schools": "Schools",
    "Shops": "Shops",
}


def build_full_image_url(path_or_url: str) -> str:
    """Ensure image URL is absolute and points to high-resolution version."""
    if not path_or_url:
        return ""
    if path_or_url.startswith("http"):
        # Replace -250.jpg thumbnail suffix with full size
        url = re.sub(r'-250\.(jpg|png|jpeg|webp)$', r'.\1', path_or_url, flags=re.IGNORECASE)
        url = re.sub(r'-thumb\.(jpg|png|jpeg|webp)$', r'.\1', url, flags=re.IGNORECASE)
        return url
    if path_or_url.startswith("/"):
        return JD_IMAGE_BASE + path_or_url
    return path_or_url


def scrape_jd_api(target_location: str, category: str, limit: int = 100, nextdocid: str = None, proxy_config = None) -> dict:
    """
    Call JustDial searchziva API directly using JWT authentication.
    Uses cursor-based pagination: pass `nextdocid` from a previous response
    to retrieve the next unique batch of listings.
    `target_location` can be a district name or a specific pincode.
    Returns dict with columns, rows, and next_cursor for chaining.
    """
    auth_token = generate_jd_bearer_token()
    device_id = str(uuid.uuid4())

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "di": device_id,
        "User-Agent": "JustDial-Android/848",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Connection": "keep-alive"
    }

    params = {
        "city": target_location,
        "state": "",
        "case": "spcall",
        "stype": "category_list",
        "search": category,
        "limit": limit,
    }

    # Cursor-based pagination: pass nextdocid to get the next page
    if nextdocid:
        params["nextdocid"] = nextdocid

    # The proxy_config is already passed into the function arguments from scrape_jwt_city

    MAX_RETRIES = 3
    data = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Regenerate token + device_id + get a fresh random proxy on each retry for a fresh identity
            current_proxy = proxy_config
            if attempt > 1:
                headers["Authorization"] = f"Bearer {generate_jd_bearer_token()}"
                headers["di"] = str(uuid.uuid4())
                if proxy_config is not None:
                    current_proxy = get_random_proxy()
                print(f"  [RETRY {attempt}/{MAX_RETRIES}] Retrying with fresh proxy IP...")
                time.sleep(2)
            resp = requests.get(JD_API_BASE, params=params, headers=headers, timeout=20, proxies=current_proxy)
            resp.raise_for_status()
            data = resp.json()
            break  # Success — exit retry loop
        except requests.exceptions.SSLError:
            try:
                resp = requests.get(JD_API_BASE, params=params, headers=headers, timeout=20, verify=False, proxies=NO_PROXY)
                data = resp.json()
                break
            except Exception as e2:
                print(f"  [ERR] SSL fallback failed (attempt {attempt}): {e2}")
        except Exception as e:
            print(f"  [ERR] API call failed for {target_location} (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt == MAX_RETRIES:
                return {"columns": [], "rows": [], "raw": {}, "next_cursor": None}

    if data is None:
        return {"columns": [], "rows": [], "raw": {}, "next_cursor": None}

    results = data.get("results", {})
    if not isinstance(results, dict):
        return {"columns": [], "rows": [], "raw": data, "next_cursor": None}

    columns = results.get("columns", [])
    rows = results.get("data", [])

    # Extract the cursor for the next page
    next_cursor = data.get("nextdocid") or None
    next_cursor_count = data.get("nextdocidcount", 0)
    # If nextdocidcount is 0, there are no more pages
    if not next_cursor_count:
        next_cursor = None

    total_count = data.get("totalNumberofResults", 0)

    return {"columns": columns, "rows": rows, "raw": data, "next_cursor": next_cursor, "total_count": total_count}


def fetch_extended_images(doc_id: str, city: str, proxy_config = None) -> dict:
    """Fetch all tabbed images (Menu, Food, Ambience, Drink, etc.) from catalogue_category.php."""
    if not doc_id:
        return {}
    
    doc_id_dot = doc_id.replace("-", ".")
    auth_token = generate_jd_bearer_token()
    device_id = str(uuid.uuid4())
    
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "di": device_id,
        "User-Agent": "JustDial-Android/848",
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive"
    }
    
    url = "https://win.justdial.com/01march2019/catalogue_category.php"
    params = {
        "docid": doc_id_dot,
        "city": city
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10, proxies=proxy_config)
        if resp.status_code == 200:
            data = resp.json()
            images_data = data.get("images", {})
            parsed_categories = {}
            seen_urls = set()
            
            # 1. Parse specific categories first
            for cat_name, cat_val in images_data.items():
                if cat_name == "All":
                    continue
                
                dn = cat_val.get("dn", ["https://images.jdmagicbox.com"])
                base_dn = dn[0] if dn else "https://images.jdmagicbox.com"
                
                cat_urls = []
                for item in cat_val.get("res", []):
                    io = item.get("io")
                    if io:
                        full_url = base_dn + io
                        full_url = build_full_image_url(full_url)
                        if full_url and full_url not in seen_urls:
                            cat_urls.append(full_url)
                            seen_urls.add(full_url)
                
                if cat_urls:
                    parsed_categories[cat_name.lower()] = cat_urls
            
            # 2. Parse "All" category and classify remaining items as "general"
            all_val = images_data.get("All", {})
            if all_val:
                dn = all_val.get("dn", ["https://images.jdmagicbox.com"])
                base_dn = dn[0] if dn else "https://images.jdmagicbox.com"
                
                general_urls = []
                for item in all_val.get("res", []):
                    io = item.get("io")
                    if io:
                        full_url = base_dn + io
                        full_url = build_full_image_url(full_url)
                        if full_url and full_url not in seen_urls:
                            general_urls.append(full_url)
                            seen_urls.add(full_url)
                
                if general_urls:
                    parsed_categories["general"] = general_urls
            
            return parsed_categories
    except Exception as e:
        print(f"  [ERR] Failed to fetch extended images for {doc_id}: {e}")
    return {}


def parse_row(columns: list, row: list, district: str, category: str) -> dict:
    """Convert a raw JustDial API row into a structured listing dict."""
    col_idx = {col: i for i, col in enumerate(columns)}

    def get(col, default=None):
        idx = col_idx.get(col)
        if idx is None or idx >= len(row):
            return default
        return row[idx]

    # Core fields
    name = str(get("name", "")).strip()
    phone = str(get("VNumber", "")).strip()
    
    # Fallback to direct mobile number from CALL button val list if virtual number is empty
    if not phone:
        vjd = get("vertical_jadoo_data", [])
        if not isinstance(vjd, list) or not vjd:
            # Try vertical object
            vertical = get("vertical", {})
            if isinstance(vertical, dict):
                vjd = vertical.get("other", {}).get("actionurl", [])
        
        if isinstance(vjd, list):
            for btn in vjd:
                if btn.get("button_text") == "CALL":
                    vals = btn.get("val", [])
                    if vals:
                        val = str(vals[0]).strip()
                        if val.startswith("91") and len(val) == 12:
                            phone = f"+(91)-{val[2:]}"
                        else:
                            phone = val
                        break

    address = str(get("NewAddress", "")).strip()
    area = str(get("area", "")).strip()
    lat = get("lat")
    lon = get("lon")
    rating = get("compRating")
    total_reviews = get("totalReviews", 0)
    doc_id = str(get("docid", "")).strip()

    # Build JustDial listing URL
    jd_url = f"https://www.justdial.com/{district}/{name.replace(' ', '-')}/{doc_id}" if doc_id else ""

    # Parse opening hours (timings)
    opstring = get("opstring", {})
    opening_hours = ""
    if isinstance(opstring, dict):
        timing = opstring.get("timing", "")
        status = opstring.get("status", "")
        if timing:
            opening_hours = timing
        elif status:
            opening_hours = status

    # Images — dimages contains full-resolution URLs
    dimages = get("dimages", [])
    orig_image = get("orig_image", "")
    dimagesthumb = get("dimagesthumb", [])

    images = []
    if isinstance(dimages, list):
        for img_url in dimages:
            full_url = build_full_image_url(img_url)
            if full_url:
                images.append(full_url)
    elif orig_image:
        full_url = build_full_image_url(orig_image)
        if full_url:
            images.append(full_url)

    # Also add orig_image if not already included
    if orig_image:
        full_url = build_full_image_url(orig_image)
        if full_url and full_url not in images:
            images.insert(0, full_url)

    # Photo count
    photo_cnt = get("photocnt", len(images))

    # WhatsApp extraction
    whatsapp = ""
    msg_num_str = get("msg_num", "")
    if msg_num_str:
        try:
            import json
            wup_list = json.loads(msg_num_str).get("wup", [])
            if wup_list:
                val = str(wup_list[0]).strip()
                if val.startswith("91") and len(val) == 12:
                    whatsapp = f"+(91)-{val[2:]}"
                else:
                    whatsapp = val
        except Exception:
            pass

    # Category
    listing_type = str(get("type", category)).strip() or category

    # Location string
    location = f"{area}, {district}" if area else district

    return {
        "name": name,
        "phone": phone,
        "whatsapp": whatsapp,
        "address": address,
        "area": area,
        "location": location,
        "district": district,
        "category": listing_type or category,
        "latitude": float(lat) if lat else None,
        "longitude": float(lon) if lon else None,
        "rating": float(rating) if rating else None,
        "reviews_count": int(total_reviews) if total_reviews else 0,
        "jd_url": jd_url,
        "doc_id": doc_id,
        "images": images,
        "photo_count": photo_cnt,
        "opening_hours": opening_hours,
    }


def save_to_db(db, listing_data: dict, category: str, proxy_config = None) -> tuple[bool, bool]:
    """Save listing to database. Returns (inserted, updated)."""
    name = listing_data["name"]
    phone = listing_data["phone"]
    district = listing_data["district"]

    if not name:
        return False, False

    # Check if listing already exists — use jd_url as primary key (always unique)
    existing = None
    jd_url = listing_data.get("jd_url", "")
    if jd_url:
        existing = db.query(models.Listing).filter(
            models.Listing.jd_url == jd_url
        ).first()
    if not existing and phone:
        existing = db.query(models.Listing).filter(
            models.Listing.phone == phone
        ).first()
    if not existing:
        existing = db.query(models.Listing).filter(
            models.Listing.name == name,
            models.Listing.address == listing_data.get("address", "")
        ).first()

    if existing:
        # Update fields if missing
        updated = False
        if not existing.latitude and listing_data["latitude"]:
            existing.latitude = listing_data["latitude"]
            updated = True
        if not existing.longitude and listing_data["longitude"]:
            existing.longitude = listing_data["longitude"]
            updated = True
        if not existing.opening_hours and listing_data.get("opening_hours"):
            existing.opening_hours = listing_data["opening_hours"]
            updated = True
        if not existing.whatsapp and listing_data.get("whatsapp"):
            existing.whatsapp = listing_data["whatsapp"]
            updated = True

        # Update category to a more specific subcategory if it is currently generic
        generic_categories = {"wedding planning", "restaurants", "hotels & restaurants", "wedding"}
        if existing.category and existing.category.lower() in generic_categories and category.lower() not in generic_categories:
            existing.category = category
            updated = True

        # Add images if missing (try categorized lookup first)
        img_count = db.query(models.ListingImage).filter_by(listing_id=existing.id).count()
        if img_count == 0:
            doc_id = listing_data.get("doc_id")
            extended_images = fetch_extended_images(doc_id, district, proxy_config=proxy_config) if doc_id else {}
            if extended_images:
                for category_name, urls in extended_images.items():
                    for url in urls:
                        db.add(models.ListingImage(listing_id=existing.id, image_path=url, category=category_name))
                updated = True
            elif listing_data.get("images"):
                for url in listing_data["images"]:
                    db.add(models.ListingImage(listing_id=existing.id, image_path=url, category="general"))
                updated = True

        if updated:
            db.commit()
        return False, updated

    # Create new listing
    new_listing = models.Listing(
        name=name,
        phone=phone,
        whatsapp=listing_data.get("whatsapp", ""),
        address=listing_data["address"],
        place=listing_data["area"],
        district=district,
        state="Kerala",
        category=category,
        latitude=str(listing_data["latitude"]) if listing_data["latitude"] is not None else None,
        longitude=str(listing_data["longitude"]) if listing_data["longitude"] is not None else None,
        jd_url=listing_data["jd_url"],
        opening_hours=listing_data["opening_hours"],
    )

    try:
        db.add(new_listing)
        db.flush()

        # Add images (try categorized lookup first)
        doc_id = listing_data.get("doc_id")
        extended_images = fetch_extended_images(doc_id, district, proxy_config=proxy_config) if doc_id else {}
        if extended_images:
            for category_name, urls in extended_images.items():
                for url in urls:
                    db.add(models.ListingImage(listing_id=new_listing.id, image_path=url, category=category_name))
        else:
            for url in listing_data["images"]:
                db.add(models.ListingImage(listing_id=new_listing.id, image_path=url, category="general"))

        db.commit()
        return True, False
    except IntegrityError:
        db.rollback()
        return False, False
    except Exception as e:
        db.rollback()
        print(f"  [ERR] DB save failed for {name}: {e}")
        return False, False


def scrape_jwt_city(district: str, category: str, pages: int = 3, limit: int = 100, dry_run: bool = False, subcategories: bool = False, use_proxy: bool = False):
    """
    Scrape JustDial using direct JWT requests for all pincodes in the district.
    Uses cursor-based pagination (nextdocid) to navigate through all result pages.
    Writes progress to the app's global scraper_logger.
    """
    from app.scraper.logger import log

    if subcategories:
        from app.scraper.constants import get_subcategories_for_main
        subcats = get_subcategories_for_main(category)
        if subcats:
            log(f"[INFO] Batch subcategory mode enabled! Found {len(subcats)} subcategories under '{category}':")
            log(f"   {', '.join(subcats)}")
            
            total_ins = 0
            total_upd = 0

            # ── Checkpoint system: resume from where we stopped ──────────────
            checkpoint_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "scrape_checkpoint.json")
            os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
            try:
                with open(checkpoint_path, "r") as f:
                    checkpoint = json.load(f)
            except Exception:
                checkpoint = {}

            def checkpoint_key(d, s):
                return f"{d.lower()}|{s.lower()}"

            def mark_done(d, s):
                checkpoint[checkpoint_key(d, s)] = True
                with open(checkpoint_path, "w") as f:
                    json.dump(checkpoint, f)

            def is_done(d, s):
                return checkpoint.get(checkpoint_key(d, s), False)
            # ─────────────────────────────────────────────────────────────────

            for idx, sub in enumerate(subcats):
                log(f"\n############################################################")
                log(f"## Subcategory [{idx+1}/{len(subcats)}]: {sub}")
                log(f"############################################################")

                # Skip if already completed in a previous run
                if is_done(district, sub):
                    log(f"  [CHECKPOINT] Already completed '{sub}' in '{district}'. Skipping!")
                    continue

                ins, upd = scrape_jwt_city(district=district, category=sub, pages=pages, limit=limit, dry_run=dry_run, subcategories=False, use_proxy=use_proxy)
                total_ins += ins
                total_upd += upd

                # Mark this subcategory as done
                mark_done(district, sub)
                log(f"  [CHECKPOINT] Saved progress: '{sub}' in '{district}' marked as done.")

            log(f"\n{'='*60}")
            log(f"  BATCH COMPLETED! Total Inserted: {total_ins} | Total Updated: {total_upd}")
            log(f"{'='*60}")
            return total_ins, total_upd
    
    log("=" * 60)
    log("  JustDial Direct API Scraper (JWT Enabled + Cursor Pagination)")
    log("=" * 60)
    log(f"  District:  {district}")
    log(f"  Category:  {category}")
    log(f"  Max pages: {pages} x up to {limit} results each")
    log(f"  Mode:      {'DRY RUN' if dry_run else 'LIVE (saving to DB)'}")
    log("=" * 60)

    # Fetch areas for district first (more effective for JustDial search query filtering)
    from app.scraper.constants import get_areas_for_district
    areas = get_areas_for_district(district)
    
    if areas and len(areas) > 1:
        log(f"[INFO] Found {len(areas)} local areas for district '{district}':")
        log(f"   {', '.join(areas)}")
        targets = areas
        use_area_query = True
    else:
        # Fallback to pincodes
        pincodes = get_pincodes_for_district(district)
        if pincodes:
            log(f"[INFO] Found {len(pincodes)} pincodes for district '{district}':")
            log(f"   {', '.join(pincodes)}")
            targets = pincodes
            use_area_query = False
        else:
            log(f"[WARN] No areas or pincodes found for '{district}'. Falling back to direct district search.")
            targets = [district]
            use_area_query = False

    db = SessionLocal() if not dry_run else None
    total_inserted = 0
    total_updated = 0

    import random

    # Determine stop flag path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    flag_path = os.path.join(current_dir, "data", "scrape_stop.flag")

    for idx, target in enumerate(targets):
        # Check stop flag before target
        if os.path.exists(flag_path):
            log("🛑 Scrape task stopped by user request.")
            break

        log(f"\n==========================================")
        log(f"[*] Scraping target {idx+1}/{len(targets)}: {target}")
        log(f"==========================================")

        # Use cursor-based pagination: start with no cursor, chain using nextdocid slices
        all_docids = []
        page_num = 0
        max_pages = pages  # max batches per pincode

        while page_num < max_pages:
            # Check stop flag inside loop
            if os.path.exists(flag_path):
                log("🛑 Scrape task stopped by user request.")
                break

            page_num += 1

            # Prepare the slice of docids for the nextdocid parameter
            next_cursor = None
            if page_num > 1:
                start_idx = (page_num - 1) * 10
                end_idx = page_num * 10
                if start_idx < len(all_docids):
                    next_cursor = ','.join(all_docids[start_idx:end_idx])
                else:
                    log("  All returned docids have been fetched. Moving to next target.")
                    break

            # Determine proxy configuration for this iteration dynamically
            proxy_config = get_random_proxy() if use_proxy else NO_PROXY

            if use_area_query:
                result = scrape_jd_api(district, f"{category} in {target}", limit=limit, nextdocid=next_cursor, proxy_config=proxy_config)
            elif target.isdigit() and len(target) == 6:
                result = scrape_jd_api(district, f"{category} {target}", limit=limit, nextdocid=next_cursor, proxy_config=proxy_config)
            else:
                result = scrape_jd_api(target, category, limit=limit, nextdocid=next_cursor, proxy_config=proxy_config)

            columns = result.get("columns", [])
            rows = result.get("rows", [])
            
            # If it's page 1, capture the full nextdocid list of docids
            if page_num == 1:
                raw_next_cursor = result.get("next_cursor")
                all_docids = raw_next_cursor.split(',') if raw_next_cursor else []
                if not all_docids and rows:
                    # Fallback: if nextdocid was empty but we got rows, populate with their docids
                    all_docids = [row[0] for row in rows]
                
                try:
                    total_count = int(result.get("total_count", 0))
                except (ValueError, TypeError):
                    total_count = 0
                    
                if total_count > 0:
                    log(f"🔎 Found {total_count} total {category} in {target}.")
                else:
                    log(f"🔎 Searching {category} in {target}...")

            if not rows:
                log("  No results returned for this batch. Moving to next target.")
                break

            log(f"  Scraping page {page_num} (got {len(rows)} results)...")
            
            # Check if there are more docids to fetch in the next page
            has_more = (page_num * 10) < len(all_docids)
            if has_more:
                log(f"  Checking page {page_num + 1} for the next batch...")
            else:
                log(f"  No more pages found (END OF RESULTS).")

            for i, row in enumerate(rows):
                listing = parse_row(columns, row, district, category)
                if not listing or not listing["name"]:
                    continue
                status = "IMG" if listing["images"] else "TXT"
                log(f"  [{i+1}] [{status}] {listing['name']} | {listing['phone']} | {len(listing['images'])} photos")

                if listing["images"]:
                    for img_idx, img in enumerate(listing["images"][:3]):
                        log(f"       [{img_idx+1}] {img[:90]}...")

                if not dry_run and db:
                    inserted, updated = save_to_db(db, listing, category, proxy_config=proxy_config)
                    if inserted:
                        total_inserted += 1
                        log(f"       → [NEW] Saved to DB ✅")
                    elif updated:
                        total_updated += 1
                        log(f"       → [UPD] Updated in DB 🔄")

            # If there's no more docids to fetch, we've exhausted this target's results
            if not has_more:
                log("  Reached last page for this target.")
                break

            # Sleep between batches to be polite
            time.sleep(random.uniform(0.8, 1.8))

        # Sleep between pincodes
        time.sleep(random.uniform(1.0, 2.5))

    if db:
        db.close()

    log(f"\n{'='*60}")
    log(f"  Done! Inserted: {total_inserted} | Updated: {total_updated}")
    log(f"{'='*60}")
    return total_inserted, total_updated


def main():
    parser = argparse.ArgumentParser(description="JustDial Direct API Scraper")
    parser.add_argument("--district", required=True, help="Target district (e.g. Palakkad)")
    parser.add_argument("--category", required=True, help="Category (e.g. Restaurants)")
    parser.add_argument("--pages", type=int, default=3, help="Number of pages to scrape per pincode (default: 3)")
    parser.add_argument("--limit", type=int, default=10, help="Results per page (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to DB, just print results")
    parser.add_argument("--subcategories", action="store_true", help="Automatically scrape all subcategories under main category")
    parser.add_argument("--use-proxy", action="store_true", help="Route API calls through Webshare proxy (useful for Cloud VMs)")
    args = parser.parse_args()

    scrape_jwt_city(
        district=args.district,
        category=args.category,
        pages=args.pages,
        limit=args.limit,
        dry_run=args.dry_run,
        subcategories=args.subcategories,
        use_proxy=args.use_proxy
    )


if __name__ == "__main__":
    main()
