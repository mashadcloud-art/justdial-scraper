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


def scrape_jd_api(target_location: str, category: str, page: int = 1, limit: int = 10) -> dict:
    """
    Call JustDial searchziva API directly using JWT authentication.
    `target_location` can be a district name or a specific pincode.
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
        "stype": "category_li",
        "search": category,
        "page": page,
        "limit": limit,
    }

    try:
        resp = requests.get(JD_API_BASE, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.SSLError:
        # Try without SSL verification as fallback
        resp = requests.get(JD_API_BASE, params=params, headers=headers, timeout=15, verify=False)
        data = resp.json()
    except Exception as e:
        print(f"  [ERR] API call failed for {target_location}: {e}")
        return {"columns": [], "rows": [], "raw": {}}

    results = data.get("results", {})
    if not isinstance(results, dict):
        return {"columns": [], "rows": [], "raw": data}

    columns = results.get("columns", [])
    rows = results.get("data", [])

    return {"columns": columns, "rows": rows, "raw": data}


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

    # Category
    listing_type = str(get("type", category)).strip() or category

    # Location string
    location = f"{area}, {district}" if area else district

    return {
        "name": name,
        "phone": phone,
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


def save_to_db(db, listing_data: dict, category: str) -> tuple[bool, bool]:
    """Save listing to database. Returns (inserted, updated)."""
    name = listing_data["name"]
    phone = listing_data["phone"]
    district = listing_data["district"]

    if not name:
        return False, False

    # Check if listing already exists by phone or name+district
    existing = None
    if phone:
        existing = db.query(models.Listing).filter(
            models.Listing.phone == phone,
            models.Listing.district == district
        ).first()
    if not existing:
        existing = db.query(models.Listing).filter(
            models.Listing.name == name,
            models.Listing.district == district
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

        # Add images if missing
        img_count = db.query(models.ListingImage).filter_by(listing_id=existing.id).count()
        if img_count == 0 and listing_data["images"]:
            for url in listing_data["images"]:
                db.add(models.ListingImage(listing_id=existing.id, image_path=url))
            updated = True

        if updated:
            db.commit()
        return False, updated

    # Create new listing
    new_listing = models.Listing(
        name=name,
        phone=phone,
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

        # Add images
        for url in listing_data["images"]:
            db.add(models.ListingImage(listing_id=new_listing.id, image_path=url))

        db.commit()
        return True, False
    except IntegrityError:
        db.rollback()
        return False, False
    except Exception as e:
        db.rollback()
        print(f"  [ERR] DB save failed for {name}: {e}")
        return False, False


def scrape_jwt_city(district: str, category: str, pages: int = 3, limit: int = 10, dry_run: bool = False):
    """
    Scrape JustDial using direct JWT requests for all pincodes in the district.
    Writes progress to the app's global scraper_logger.
    """
    from app.scraper.logger import log
    
    log("=" * 60)
    log("  JustDial Direct API Scraper (JWT Enabled)")
    log("=" * 60)
    log(f"  District:  {district}")
    log(f"  Category:  {category}")
    log(f"  Pages/Pin: {pages} x {limit} results")
    log(f"  Mode:      {'DRY RUN' if dry_run else 'LIVE (saving to DB)'}")
    log("=" * 60)

    # Fetch pincodes for district
    pincodes = get_pincodes_for_district(district)
    if pincodes:
        log(f"[INFO] Found {len(pincodes)} pincodes for district '{district}':")
        log(f"   {', '.join(pincodes)}")
        targets = pincodes
    else:
        log(f"[WARN] No pincodes found in database for '{district}'. Falling back to direct district search.")
        targets = [district]

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

        for page in range(1, pages + 1):
            # Check stop flag inside loop
            if os.path.exists(flag_path):
                break

            log(f"--- Page {page}/{pages} ---")
            if target.isdigit() and len(target) == 6:
                result = scrape_jd_api(district, f"{category} {target}", page=page, limit=limit)
            else:
                result = scrape_jd_api(target, category, page=page, limit=limit)

            columns = result.get("columns", [])
            rows = result.get("rows", [])

            if not rows:
                log("  No results returned for this page. Moving to next target.")
                break

            log(f"  Got {len(rows)} results from API.")

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
                    inserted, updated = save_to_db(db, listing, category)
                    if inserted:
                        total_inserted += 1
                    elif updated:
                        total_updated += 1

            # Sleep between pages to be polite
            time.sleep(random.uniform(0.8, 1.8))

        # Sleep between pincodes
        time.sleep(random.uniform(1.0, 2.5))

    if db:
        db.close()

    log(f"\n{'='*60}")
    log(f"  Done! Inserted: {total_inserted} | Updated: {total_updated}")
    log(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="JustDial Direct API Scraper")
    parser.add_argument("--district", required=True, help="Target district (e.g. Palakkad)")
    parser.add_argument("--category", required=True, help="Category (e.g. Restaurants)")
    parser.add_argument("--pages", type=int, default=3, help="Number of pages to scrape per pincode (default: 3)")
    parser.add_argument("--limit", type=int, default=10, help="Results per page (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to DB, just print results")
    args = parser.parse_args()

    scrape_jwt_city(
        district=args.district,
        category=args.category,
        pages=args.pages,
        limit=args.limit,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
