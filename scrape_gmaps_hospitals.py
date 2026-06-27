"""
Google Maps Kerala Hospital Scraper
===================================
- Searches Google Maps town-by-town using pincodes for a target district.
- Extracts name, coordinates, rating, address, phone number, and website.
- Deduplicates against existing listings in the Supabase database.
- Saves new listings with details and markers.
- Commits changes to the database immediately after each pincode is processed.

Usage:
  python scrape_gmaps_hospitals.py --district Kasaragod --limit-pins 3             # Dry run (default)
  python scrape_gmaps_hospitals.py --district Kasaragod --limit-pins 3 --live      # Live write to Supabase
"""

import sys
import os
import re
import argparse
import asyncio
from collections import defaultdict
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app import models
from app.api.pincodes import get_pincodes_for_district

# Clean up helper
_STRIP = re.compile(r"[^a-z0-9]")

def clean_word(w):
    return _STRIP.sub("", w.lower())

def expand_hospital_name(name: str) -> str:
    """Expand standard abbreviations in hospital name prefixes to full text."""
    if not name:
        return ""
    if name.startswith("TH "):
        return "Taluk Hospital " + name[3:]
    if name.startswith("THQH "):
        return "Taluk Headquarters Hospital " + name[5:]
    if name.startswith("DH "):
        return "District Hospital " + name[3:]
    if name.startswith("GH "):
        return "General Hospital " + name[3:]
    if name.startswith("W&C ") or name.startswith("W & C "):
        prefix_len = 4 if name.startswith("W&C ") else 6
        return "Women and Children Hospital " + name[prefix_len:]
    return name

async def scrape_pincode_hospitals(page, pincode: str, max_photos: int = 1):
    search_query = f"hospitals in {pincode} Kerala"
    print(f"\n[Search] Query: '{search_query}'")
    
    url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)
    
    panel_selector = "div[role='feed']"
    
    # Scroll results panel to load all items
    scroll_count = 0
    while scroll_count < 8:
        panel = await page.query_selector(panel_selector)
        if not panel:
            break
        await page.evaluate("document.querySelector(\"div[role='feed']\").scrollBy(0, 1000)")
        await page.wait_for_timeout(1000)
        content = await page.content()
        if "You've reached the end of the list" in content:
            break
        scroll_count += 1

    # Extract listing elements
    feed_el = await page.query_selector(panel_selector)
    if not feed_el:
        print("  -> No results feed found for this pincode.")
        return []
        
    listings = await feed_el.query_selector_all("a[href*='/maps/place/']")
    place_urls = []
    for link in listings:
        href = await link.get_attribute("href")
        if href and href not in place_urls:
            place_urls.append(href)
            
    print(f"  -> Discovered {len(place_urls)} places in feed.")
    
    results = []
    for index, place_url in enumerate(place_urls):
        try:
            print(f"  -> Processing place {index+1}/{len(place_urls)}...")
            
            # Go directly to place URL
            await page.goto(place_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)
            
            # Extract coordinates from URL
            coords_match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", place_url)
            if not coords_match:
                # Try fallback data pattern coords
                coords_match = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", place_url)
                
            latitude = coords_match.group(1) if coords_match else None
            longitude = coords_match.group(2) if coords_match else None
            
            # Extract Name
            name_el = await page.query_selector("h1.DUwDvf")
            name = await name_el.inner_text() if name_el else "Unknown Name"
            name = expand_hospital_name(name.strip())
            
            # Extract Rating
            rating_el = await page.query_selector("div.F7nice > span > span[aria-hidden='true']")
            rating = await rating_el.inner_text() if rating_el else None
            
            # Extract Reviews Count
            reviews_text = await page.evaluate("() => document.querySelector('div.F7nice')?.innerText")
            reviews_count = None
            if reviews_text:
                rev_match = re.search(r"\(([\d,]+)\)", reviews_text)
                if rev_match:
                    reviews_count = rev_match.group(1).replace(",", "")
            
            # Extract Subcategory/Category type
            subcat_el = await page.query_selector("button[class*='D7m2K']")
            subcategory = await subcat_el.inner_text() if subcat_el else "Hospital"
            
            # Extract Address
            addr_el = await page.query_selector("button[data-item-id='address'] div.Io6YTe")
            address = await addr_el.inner_text() if addr_el else ""
            
            # Extract Phone
            phone = ""
            phone_el = await page.query_selector("button[data-item-id^='phone:tel:']")
            if phone_el:
                phone_id = await phone_el.get_attribute("data-item-id")
                phone = phone_id.replace("phone:tel:", "").strip()
            
            # Extract Website
            website = ""
            web_el = await page.query_selector("a[data-item-id='authority']")
            if web_el:
                website = await web_el.get_attribute("href")
            
            # Extract main cover image URL from Google Maps
            image_url = ""
            # Try multiple selectors for hero image
            hero_selectors = [
                "button[jsaction*='heroHeaderImage'] img",
                "button.ao3bfe img",
                "div[jsaction*='heroHeaderImage'] img",
                "img[src*='googleusercontent']",
                "div.m6QErb img"
            ]
            for sel in hero_selectors:
                img_el = await page.query_selector(sel)
                if img_el:
                    src = await img_el.get_attribute("src")
                    if src and "googleusercontent" in src:
                        image_url = src
                        break
            
            # Helper: deduplicate Google image URLs by stripping scale params
            def canonical_img_url(url):
                """Strip =w...-h... scale params to get the base image identifier."""
                import re as _re
                return _re.sub(r'=w\d+-h\d+.*$', '', url)
            
            def is_large_img(url):
                """Reject tiny thumbnails (w32 / h32 / p-k-no patterns)."""
                return 'w32-h32' not in url and 'p-k-no' not in url and 'w48-h48' not in url and 'w64-h64' not in url
            
            # Extract additional gallery images if requested
            image_urls = []
            seen_canonical = set()
            if image_url and is_large_img(image_url):
                image_urls.append(image_url)
                seen_canonical.add(canonical_img_url(image_url))
            
            # Try to get more photos with a timeout to prevent hanging
            try:
                if max_photos > 1 or len(image_urls) == 0:
                    # Try clicking the Photos tab button first, then hero image
                    photos_tab_clicked = False
                    # Try multiple selectors for photos button
                    photo_button_selectors = [
                        "button[jsaction*='pane.heroHeaderImage.photos']",
                        "div.YkuOqf button",
                        "button[aria-label*='photo']",
                        "button[aria-label*='Photo']",
                        "button[class*='gallery']",
                        "button[jsaction*='photos']"
                    ]
                    click_target = None
                    for sel in photo_button_selectors:
                        btn = await page.query_selector(sel)
                        if btn:
                            click_target = btn
                            break
                    
                    if not click_target:
                        # Try hero image button if no photo tab found
                        img_btn_selectors = [
                            "button[jsaction*='heroHeaderImage']",
                            "button.ao3bfe",
                            "div[jsaction*='heroHeaderImage']"
                        ]
                        for sel in img_btn_selectors:
                            btn = await page.query_selector(sel)
                            if btn:
                                click_target = btn
                                break
                        
                    if click_target:
                        try:
                            await click_target.click(timeout=10000)  # Shorter timeout for click
                            await page.wait_for_timeout(3000)  # Wait less time for gallery
                            photos_tab_clicked = True
                            
                            # Scroll gallery in a loop to load more images
                            scroll_count = 0
                            previous_count = len(image_urls)
                            while len(image_urls) < max_photos and scroll_count < 100:
                                # Scroll all gallery containers
                                await page.evaluate("""
                                    document.querySelectorAll('div.m6QErb, div[role=main], div[role=feed], div[class*="gallery"], div[class*="scroll"]').forEach(
                                        function(el) { el.scrollBy(0, 3000); }
                                    );
                                """)
                                await page.wait_for_timeout(1000)  # Wait less after each scroll
                                
                                # Collect large images only
                                gallery_srcs = await page.evaluate("""
                                    () => Array.from(document.querySelectorAll('img'))
                                        .map(function(i) { return i.src; })
                                        .filter(function(s) {
                                            return s && s.includes('googleusercontent') &&
                                                   s.indexOf('w32-h32') === -1 &&
                                                   s.indexOf('p-k-no') === -1 &&
                                                   s.indexOf('w48-h48') === -1 &&
                                                   s.indexOf('w64-h64') === -1;
                                        })
                                """)
                                added = 0
                                for g_src in gallery_srcs:
                                    base = canonical_img_url(g_src)
                                    if base not in seen_canonical:
                                        seen_canonical.add(base)
                                        image_urls.append(g_src)
                                        added += 1
                                        if len(image_urls) >= max_photos:
                                            break
                                            
                                if added == 0:
                                    # No new images loaded, stop scrolling
                                    break
                                previous_count = len(image_urls)
                                scroll_count += 1
                        except Exception as e:
                            print(f"     [WARN] Gallery scraping failed: {e}")
            except Exception as e:
                print(f"     [WARN] Photo extraction failed: {e}")
            
            # If we still have no images, try extracting from page without clicking
            if len(image_urls) == 0:
                try:
                    all_imgs = await page.evaluate("""
                        () => Array.from(document.querySelectorAll('img'))
                            .map(i => i.src)
                            .filter(s => 
                                s && 
                                s.includes('googleusercontent') && 
                                !s.includes('w32-h32') && 
                                !s.includes('p-k-no') &&
                                !s.includes('w48-h48') &&
                                !s.includes('w64-h64')
                            );
                    """)
                    for src in all_imgs[:max_photos]:
                        base = canonical_img_url(src)
                        if base not in seen_canonical:
                            seen_canonical.add(base)
                            image_urls.append(src)
                            if len(image_urls) >= max_photos:
                                break
                except Exception as e:
                    print(f"     [WARN] Fallback image extraction failed: {e}")
                    
            # Ensure we have at least one image in image_urls
            if len(image_urls) == 0 and image_url and is_large_img(image_url):
                image_urls.append(image_url)
            
            results.append({
                "name": name,
                "address": address,
                "phone": phone,
                "website": website,
                "image_url": image_url,
                "image_urls": image_urls,
                "category": "Hospitals",
                "subcategory": subcategory,
                "latitude": latitude,
                "longitude": longitude,
                "rating": rating,
                "reviews_count": reviews_count,
                "place_url": place_url
            })
            print(f"     [OK] {name} | Phone: {phone} | Lat/Lng: {latitude},{longitude} | Photos: {len(image_urls)}")
            
        except Exception as e:
            print(f"     [ERR] Failed to parse place: {e}")
            
    return results

def process_and_commit_hospitals(db, hospitals, district: str, live: bool):
    """Processes extracted hospitals and writes them immediately to the DB."""
    if not hospitals:
        return
        
    print(f"  -> Merging {len(hospitals)} hospitals into Supabase...")
    inserted_count = 0
    updated_count = 0
    
    for h in hospitals:
        # Check by exact Google Maps URL first
        existing = db.query(models.Listing).filter(models.Listing.jd_url == h["place_url"]).first()
        
        # Or check by name + district coordinates fuzzy match
        if not existing and h["latitude"] and h["longitude"]:
            existing = db.query(models.Listing).filter(
                models.Listing.category == "Hospitals",
                models.Listing.district == district,
                models.Listing.name.ilike(h["name"])
            ).first()
            
        if existing:
            # Match found: enrich existing coordinates and details if empty
            updated = False
            if (not existing.latitude or existing.latitude.strip() == "") and h["latitude"]:
                existing.latitude = str(h["latitude"])
                updated = True
            if (not existing.longitude or existing.longitude.strip() == "") and h["longitude"]:
                existing.longitude = str(h["longitude"])
                updated = True
            if (not existing.phone or existing.phone.strip() == "") and h["phone"]:
                existing.phone = h["phone"]
                updated = True
                
            if updated:
                updated_count += 1
                
            # Add rating/reviews/website amenities if they don't exist
            existing_amenities = {a.category: a.value for a in existing.amenities}
            
            new_amenities = [
                ("DataSource", "GoogleMapsScraper"),
            ]
            if h["rating"]:
                new_amenities.append(("Google Rating", str(h["rating"])))
            if h["reviews_count"]:
                new_amenities.append(("Google Reviews Count", str(h["reviews_count"])))
            if h["website"]:
                new_amenities.append(("Website", h["website"]))
                
            for cat, val in new_amenities:
                if cat not in existing_amenities and live:
                    db.add(models.Amenity(
                        listing_id=existing.id,
                        category=cat,
                        value=val
                    ))
            
            # Update images if listing has no images
            if h["image_urls"] and live:
                has_image = db.query(models.ListingImage).filter(models.ListingImage.listing_id == existing.id).first()
                if not has_image:
                    for idx, img_url in enumerate(h["image_urls"]):
                        db.add(models.ListingImage(
                            listing_id=existing.id,
                            image_path=img_url,
                            category="general",
                            is_primary=(idx == 0)
                        ))
        else:
            # Create new listing
            if live:
                new_listing = models.Listing(
                    name=h["name"],
                    address=h["address"],
                    phone=h["phone"],
                    whatsapp="",
                    jd_url=h["place_url"],
                    category="Hospitals",
                    subcategory=h["subcategory"],
                    normalized_category="Health & Medical",
                    opening_hours="24 Hours",
                    district=district,
                    state="Kerala",
                    place=h["address"].split(",")[-2].strip() if len(h["address"].split(",")) > 2 else "",
                    latitude=str(h["latitude"]) if h["latitude"] else "",
                    longitude=str(h["longitude"]) if h["longitude"] else "",
                )
                db.add(new_listing)
                db.flush()
                
                # Add amenities
                amenities_to_add = [
                    ("DataSource", "GoogleMapsScraper"),
                ]
                if h["rating"]:
                    amenities_to_add.append(("Google Rating", str(h["rating"])))
                if h["reviews_count"]:
                    amenities_to_add.append(("Google Reviews Count", str(h["reviews_count"])))
                if h["website"]:
                    amenities_to_add.append(("Website", h["website"]))
                    
                for cat, val in amenities_to_add:
                    db.add(models.Amenity(
                        listing_id=new_listing.id,
                        category=cat,
                        value=val
                    ))
                
                # Add gallery image URLs to listing_images
                if h["image_urls"]:
                    for idx, img_url in enumerate(h["image_urls"]):
                        db.add(models.ListingImage(
                            listing_id=new_listing.id,
                            image_path=img_url,
                            category="general",
                            is_primary=(idx == 0)
                        ))
            inserted_count += 1

    if live:
        print(f"  -> Committing modifications (inserts: {inserted_count}, updates: {updated_count}) to Supabase...")
        db.commit()
        print("  -> Done for this pincode!")
    else:
        print(f"  [Preview Pincode] (Dry run - nothing written)")
        print(f"    New listings: {inserted_count}, Updates: {updated_count}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", required=True, help="Target district (e.g. Kasaragod)")
    parser.add_argument("--limit-pins", type=int, default=None, help="Limit number of pincodes to scrape")
    parser.add_argument("--max-photos", type=int, default=1, help="Max photos to extract per hospital (default: 1)")
    parser.add_argument("--live", action="store_true", help="Write changes directly to database")
    args = parser.parse_args()
    
    db = SessionLocal()
    
    print("=" * 60)
    print("GOOGLE MAPS KERALA HOSPITAL SCRAPER")
    print("=" * 60)
    print(f"District: {args.district}")
    print(f"Max Photos per Place: {args.max_photos}")
    print(f"Mode: {'LIVE (writing to DB)' if args.live else 'DRY RUN (no writes)'}")
    print()
    
    # 1. Fetch pincodes
    district_query = args.district
    pincodes = get_pincodes_for_district(district_query)
    if not pincodes and district_query.lower() == "kasaragod":
        print("Retrying pincode search with spelling: 'Kasargod'...")
        district_query = "Kasargod"
        pincodes = get_pincodes_for_district(district_query)
        
    if not pincodes:
        print("Error: No pincodes found. Check connection or spelling of district.")
        db.close()
        return
        
    print(f"Found {len(pincodes)} pincodes in district {args.district}.")
    if args.limit_pins:
        pincodes = pincodes[:args.limit_pins]
        print(f"Limiting search to first {len(pincodes)} pincodes.")
    
    # Initialize Playwright browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US"
        )
        page = await context.new_page()
        
        for index, pin in enumerate(pincodes):
            print(f"\n--- Pincode {index+1}/{len(pincodes)}: {pin} ---")
            hospitals = await scrape_pincode_hospitals(page, pin, max_photos=args.max_photos)
            if hospitals:
                process_and_commit_hospitals(db, hospitals, args.district, args.live)
            
        await browser.close()
        
    print("\nScraping and database sync complete!")
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
