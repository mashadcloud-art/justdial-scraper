"""
Google Maps Kerala General Scraper
==================================
- Searches Google Maps town-by-town using pincodes for a target district.
- Supports arbitrary categories (e.g. Restaurants, Cafes, Hospitals, Dentists).
- Extracts name, coordinates, rating, address, phone number, and website.
- Deduplicates against existing listings in the Supabase database.
- Saves new listings with details and markers.
- Commits changes to the database immediately after each pincode is processed.

Usage:
  python scrape_gmaps_general.py --district Kasaragod --query "restaurants" --category "Restaurants" --normalized-category "Food & Restaurants" --limit-pins 3             # Dry run (default)
  python scrape_gmaps_general.py --district Kasaragod --query "restaurants" --category "Restaurants" --normalized-category "Food & Restaurants" --limit-pins 3 --live      # Live write to Supabase
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
from sqlalchemy import func
import json

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

async def extract_gmaps_menu(browser, place_url: str) -> list:
    """Clicks the digital menu tab on a temporary mobile browser context and parses dish items across all tabs."""
    menu_items = []
    mobile_context = None
    try:
        # Create a temporary mobile context in the background
        mobile_context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36",
            viewport={"width": 393, "height": 851},
            locale="en-US"
        )
        page = await mobile_context.new_page()
        
        # Navigate to place details page over mobile viewport
        # Force English locale params
        if '?' in place_url:
            if 'hl=' in place_url:
                nav_url = re.sub(r'hl=[a-z]{2}(-[A-Z]{2})?', 'hl=en', place_url)
            else:
                nav_url = place_url + '&hl=en'
        else:
            nav_url = place_url + '?hl=en'
            
        await page.goto(nav_url, wait_until="commit", timeout=60000)
        await page.wait_for_timeout(4000)
        
        # Dismiss any mobile "Keep using web" overlay if present
        keep_web_btn = await page.query_selector("button:has-text('Keep using web')")
        if keep_web_btn:
            await keep_web_btn.click()
            await page.wait_for_timeout(1000)
            
        # Try to click on the "Menu" tab / button inside the place details panel
        menu_tab = await page.query_selector("button:has-text('Menu')")
        if not menu_tab:
            menu_tab = await page.query_selector("div[role='tab']:has-text('Menu')")
        if not menu_tab:
            menu_tab = await page.query_selector("span:has-text('Menu')")
            
        if menu_tab:
            # Scroll to view and click it
            await menu_tab.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
            await menu_tab.click()
            await page.wait_for_timeout(3500) # Allow items to load
            
            # Find all category tab elements inside the menu panel
            category_tab_selectors = [
                "div[role='tablist'] div[role='tab']",
                "div[role='tablist'] button",
                "div[role='tablist'] span",
                "button[aria-selected]",
                "div[aria-selected]"
            ]
            
            tabs_to_click = []
            for sel in category_tab_selectors:
                elements = await page.query_selector_all(sel)
                if elements and len(elements) > 1:
                    for el in elements:
                        text = (await el.inner_text() or "").strip()
                        if text and text.lower() != "more" and text.lower() != "menu":
                            tabs_to_click.append(el)
                    if tabs_to_click:
                        break
            
            # Fallback: if no tabs detected, process once (single list view)
            if not tabs_to_click:
                tabs_to_click = [None]
                
            for tab in tabs_to_click:
                if tab:
                    try:
                        tab_text = (await tab.inner_text() or "").strip()
                        await tab.click()
                        await page.wait_for_timeout(1800) # Wait for category content slide transition
                    except Exception:
                        pass
                        
                # Extract names and prices of dishes currently visible in the DOM
                extracted = await page.evaluate("""
                    () => {
                        let items = [];
                        let elements = document.querySelectorAll('*');
                        elements.forEach(el => {
                            if (el.innerText && el.innerText.includes('₹') && el.children.length === 0) {
                                let parent = el.parentElement;
                                let container = parent;
                                for (let i = 0; i < 3; i++) {
                                    if (container.parentElement) {
                                        container = container.parentElement;
                                    }
                                }
                                if (container) {
                                    let lines = container.innerText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                                    if (lines.length >= 2) {
                                        let is_veg = true;
                                        let imgs = container.querySelectorAll('img');
                                        imgs.forEach(img => {
                                            let src = (img.getAttribute('src') || '').toLowerCase();
                                            let alt = (img.getAttribute('alt') || '').toLowerCase();
                                            if (src.includes('non') || alt.includes('non') || src.includes('meat') || alt.includes('meat')) {
                                                is_veg = false;
                                            }
                                        });
                                        items.push({
                                            lines: lines,
                                            is_veg: is_veg
                                        });
                                    }
                                }
                            }
                        });
                        return items;
                    }
                """)
                
                # Process extracted lines into structured dictionary items
                for item in extracted:
                    lines = item["lines"]
                    is_veg = item["is_veg"]
                    name = lines[0]
                    price = "0"
                    for line in lines[1:]:
                        if "₹" in line:
                            price_match = re.search(r"₹\s*([\d,]+(\.\d+)?)", line)
                            if price_match:
                                price = price_match.group(1).replace(",", "")
                                break
                    
                    if name and not any(m["name"].lower() == name.lower() for m in menu_items):
                        menu_items.append({
                            "name": name,
                            "price": price,
                            "is_veg": is_veg
                        })
                        
    except Exception as e:
        print(f"     [WARN] Digital Menu extraction failed: {e}")
    finally:
        if mobile_context:
            await mobile_context.close()
        
    return menu_items

async def scrape_pincode_places(browser, page, pincode: str, query: str, max_photos: int = 1, category_name: str = "", db = None, processed_urls = None):
    if pincode and pincode.strip():
        search_query = f"{query} in {pincode} Kerala"
    else:
        search_query = f"{query} Kerala"
    print(f"\n[Search] Query: '{search_query}'")
    
    url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}?hl=en"
    await page.goto(url, wait_until="commit", timeout=60000)
    await page.wait_for_timeout(4000)
    
    panel_selector = "div[role='feed']"
    
    # Check if page loaded a place page directly (i.e. name header exists or URL matches place details)
    direct_name_el = await page.query_selector("h1.DUwDvf")
    feed_exists = await page.query_selector(panel_selector)
    is_direct_place_url = "/maps/place/" in page.url or "/place/" in page.url
    if (direct_name_el or is_direct_place_url) and not feed_exists:
        print("  -> Direct place details page loaded. Processing single result...")
        place_urls = [page.url]
    else:
        # Check if we have feed container (desktop view)
        if feed_exists:
            # Scroll results panel to load all items (desktop)
            scroll_count = 0
            while scroll_count < 8:
                panel = await page.query_selector(panel_selector)
                if not panel:
                    break
                await page.evaluate('document.querySelector("div[role=\'feed\']").scrollBy(0, 1000)')
                await page.wait_for_timeout(1000)
                content = await page.content()
                if "You've reached the end of the list" in content:
                    break
                scroll_count += 1

            feed_el = await page.query_selector(panel_selector)
            listings = await feed_el.query_selector_all("a[href*='/maps/place/']")
            place_urls = []
            for link in listings:
                href = await link.get_attribute("href")
                if href and href not in place_urls:
                    place_urls.append(href)
        else:
            # Fallback for mobile view list:
            # Scroll the correct scrollable list container rather than window body
            print("  -> Desktop feed panel not found. Scrolling mobile list container...")
            scroll_count = 0
            while scroll_count < 6:
                await page.evaluate("""
                    () => {
                        // Find scrollable container (often has class with overflow-y: auto)
                        let divs = Array.from(document.querySelectorAll('div'));
                        let scrollable = divs.find(d => {
                            let style = window.getComputedStyle(d);
                            return (style.overflowY === 'auto' || style.overflowY === 'scroll') && d.scrollHeight > d.clientHeight;
                        });
                        if (scrollable) {
                            scrollable.scrollBy(0, 1000);
                        } else {
                            window.scrollBy(0, 1000);
                        }
                    }
                """)
                await page.wait_for_timeout(1500)
                scroll_count += 1
                
            # Grab all place detail URLs across the entire page DOM
            listings = await page.query_selector_all("a[href*='/maps/place/']")
            if not listings:
                listings = await page.query_selector_all("a[href*='/place/']")
                
            place_urls = []
            for link in listings:
                href = await link.get_attribute("href")
                if href and href not in place_urls:
                    place_urls.append(href)
                    
            if not place_urls:
                # Last resort fallback: check if we are redirected to a place card directly
                direct_h1 = await page.query_selector("h1")
                if direct_h1:
                    print("  -> Fallback: Single place header found on mobile.")
                    place_urls = [page.url]
                else:
                    print("  -> No results feed found for this pincode.")
                    return []
            
    print(f"  -> Discovered {len(place_urls)} places in feed.")
    
    results = []
    for index, place_url in enumerate(place_urls):
        try:
            # 1. Skip if already processed in this memory session
            if processed_urls is not None and place_url in processed_urls:
                print(f"  -> Skipping place {index+1}/{len(place_urls)} (already processed in this run)")
                continue
                
            # 2. Skip if already exists in the database
            if db is not None:
                existing = db.query(models.Listing).filter(models.Listing.jd_url == place_url).first()
                if existing:
                    print(f"  -> Skipping place {index+1}/{len(place_urls)} (already exists in database)")
                    if processed_urls is not None:
                        processed_urls.add(place_url)
                    continue

            print(f"  -> Processing place {index+1}/{len(place_urls)}...")
            
            # Go directly to place URL, force English locale
            # Preserve existing URL params (especially data= with place ID) and add/replace hl=en
            if '?' in place_url:
                if 'hl=' in place_url:
                    nav_url = re.sub(r'hl=[a-z]{2}(-[A-Z]{2})?', 'hl=en', place_url)
                else:
                    nav_url = place_url + '&hl=en'
            else:
                nav_url = place_url + '?hl=en'
                
            # Skip page.goto if we are already loaded on the exact page
            current_url = page.url
            if current_url.split("?")[0].rstrip("/") != nav_url.split("?")[0].rstrip("/"):
                await page.goto(nav_url, wait_until="commit", timeout=60000)
            
            # Wait for place details to fully render (name must appear in h1)
            try:
                await page.wait_for_function(
                    "() => { var el = document.querySelector('h1.DUwDvf'); return el && el.innerText.trim().length > 0; }",
                    timeout=10000
                )
            except Exception:
                # Fallback: wait extra time if name didn't appear
                await page.wait_for_timeout(5000)
            await page.wait_for_timeout(1500)  # Extra settle time for images
            
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
            if category_name.lower() == "hospitals":
                name = expand_hospital_name(name.strip())
            else:
                name = name.strip()
            
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
            subcategory = await subcat_el.inner_text() if subcat_el else category_name
            
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
                
            # Extract Menu Link
            menu_url = ""
            menu_el = await page.query_selector("a[data-item-id='menu']")
            if not menu_el:
                # Fallback: look for 'Order Online' or 'Menu' text links
                menu_el = await page.query_selector("a[jsaction*='pane.menu']")
            if menu_el:
                menu_url = await menu_el.get_attribute("href")
            
            # Extract Service Attributes (Dine-in, Takeaway, Delivery, etc.)
            service_attrs = []
            try:
                service_attrs = await page.evaluate("""
                    () => {
                        var attrs = [];
                        // LTs0Rc = amenities/service attribute rows
                        var rows = document.querySelectorAll('div.LTs0Rc');
                        rows.forEach(function(row) {
                            var label = row.querySelector('span.RkvNed');
                            var check = row.querySelector('span.uyM3Hb, .hpLkke');
                            if (label) {
                                var hasCheck = check !== null;
                                attrs.push((hasCheck ? '' : 'No ') + label.innerText.trim());
                            }
                        });
                        // Also try iNvpkb containers (attribute groups)
                        if (attrs.length === 0) {
                            var spans = document.querySelectorAll('div.iNvpkb span.RkvNed');
                            spans.forEach(function(s) { attrs.push(s.innerText.trim()); });
                        }
                        return attrs.filter(function(a) { return a.length > 0; });
                    }
                """)
            except Exception:
                pass
            
            # Helper: deduplicate Google image URLs by stripping scale params
            def canonical_img_url(url):
                """Strip =w...-h... scale params to get the base image identifier."""
                import re as _re
                return _re.sub(r"=w\d+-h\d+.*$", "", url)
            
            def is_large_img(url):
                """Reject tiny thumbnails (w32 / h32 / p-k-no patterns)."""
                return 'w32-h32' not in url and 'p-k-no' not in url and 'w48-h48' not in url and 'w64-h64' not in url
            
            # GALLERY PHOTO EXTRACTION: Click into the photo gallery to get multiple images
            image_urls = []
            seen_canonical = set()
            try:
                # First try to click the "All photos" / hero image button to open gallery
                if max_photos > 1:
                    gallery_opened = False
                    gallery_selectors = [
                        "button[jsaction*='heroHeaderImage']",
                        "div[jsaction*='heroHeaderImage']",
                        "button.aoRNLd",
                        "div.RZ66Rb",
                    ]
                    for sel in gallery_selectors:
                        try:
                            btn = await page.query_selector(sel)
                            if btn:
                                await btn.click()
                                await page.wait_for_timeout(2500)
                                gallery_opened = True
                                break
                        except Exception:
                            pass

                    if gallery_opened:
                        # Scroll the gallery aggressively to load ALL lazy images
                        prev_count = 0
                        for scroll_round in range(15):
                            try:
                                # Scroll the gallery container, not the page
                                await page.evaluate("""
                                    () => {
                                        var container = document.querySelector('.X98S3d') 
                                            || document.querySelector('[jsname="bnGXge"]')
                                            || document.querySelector('.DkEaL')
                                            || document.scrollingElement;
                                        if (container) container.scrollTop += 800;
                                        else window.scrollBy(0, 800);
                                    }
                                """)
                                await page.wait_for_timeout(600)
                            except Exception:
                                break
                            # Check if new images loaded
                            cur_count = await page.evaluate("""
                                () => document.querySelectorAll('img[src*="googleusercontent"]').length
                            """)
                            if cur_count == prev_count and scroll_round > 3:
                                break  # No more images loading
                            prev_count = cur_count

                        # Also try clicking "Menu" and "Food & drink" tabs for extra images
                        for tab_label in ["Menu", "Food"]:
                            try:
                                tab = await page.query_selector(f'div[aria-label*="{tab_label}"]')
                                if tab:
                                    await tab.click()
                                    await page.wait_for_timeout(1500)
                                    # Scroll this tab too
                                    for _ in range(5):
                                        await page.evaluate("""
                                            () => {
                                                var c = document.querySelector('.X98S3d') || document.scrollingElement;
                                                if (c) c.scrollTop += 800;
                                                else window.scrollBy(0, 800);
                                            }
                                        """)
                                        await page.wait_for_timeout(400)
                            except Exception:
                                pass

                        # Click back to "All" tab
                        try:
                            all_tab = await page.query_selector('div[aria-label*="All"]')
                            if all_tab:
                                await all_tab.click()
                                await page.wait_for_timeout(500)
                        except Exception:
                            pass

                # Now grab all googleusercontent images from the page
                all_imgs = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('img'))
                        .map(i => i.src)
                        .filter(s => 
                            s && 
                            s.includes('googleusercontent') && 
                            !s.includes('w32-h32') && 
                            !s.includes('p-k-no') &&
                            !s.includes('w48-h48') &&
                            !s.includes('w64-h64') &&
                            !s.includes('w20-h20') &&
                            !s.includes('w34-h34') &&
                            !s.includes('w200-h200')
                        );
                """)

                # Also try background-image style elements (gallery thumbnails)
                try:
                    bg_imgs = await page.evaluate("""
                        () => {
                            var results = [];
                            var elements = document.querySelectorAll('[style*="googleusercontent"]');
                            elements.forEach(function(el) {
                                var style = el.getAttribute('style') || '';
                                var match = style.match(/url\\("?(https?:\\/\\/[^"')]+googleusercontent[^"')]+)"?\\)/);
                                if (match) results.push(match[1]);
                            });
                            return results;
                        }
                    """)
                    all_imgs = all_imgs + bg_imgs
                except Exception:
                    pass

                for src in all_imgs:
                    if len(image_urls) >= max_photos:
                        break
                    base = canonical_img_url(src)
                    if base not in seen_canonical and is_large_img(src):
                        seen_canonical.add(base)
                        # Force large resolution — strip thumbnail params and add large size
                        large_url = base + "=w1200-h900"
                        image_urls.append(large_url)

                # If gallery was opened, go back to place detail page
                if max_photos > 1 and len(image_urls) > 0:
                    try:
                        await page.go_back(wait_until="domcontentloaded", timeout=10000)
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass

            except Exception as e:
                print(f"     [WARN] Gallery photo extraction failed: {e}")
            
            # Fallback: try getting hero image if we have none
            image_url = image_urls[0] if image_urls else ""
            if len(image_urls) == 0:
                try:
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
                            if src and "googleusercontent" in src and is_large_img(src):
                                image_urls.append(src)
                                image_url = src
                                break
                except Exception as e:
                    print(f"     [WARN] Hero image fallback failed: {e}")
            
            # Extract digital menu if restaurant category (runs in temporary background mobile context)
            menu_items = []
            if category_name.lower() == "restaurants":
                menu_items = await extract_gmaps_menu(browser, place_url)

            results.append({
                "name": name,
                "address": address,
                "phone": phone,
                "website": website,
                "menu_url": menu_url,
                "service_attrs": service_attrs,
                "image_url": image_url,
                "image_urls": image_urls,
                "menu_items": menu_items,
                "category": category_name,
                "subcategory": subcategory,
                "latitude": latitude,
                "longitude": longitude,
                "rating": rating,
                "reviews_count": reviews_count,
                "place_url": place_url
            })
            if processed_urls is not None:
                processed_urls.add(place_url)
            print(f"     [OK] {name} | Phone: {phone} | Lat/Lng: {latitude},{longitude} | Photos: {len(image_urls)} | Services: {len(service_attrs)}")
            
        except Exception as e:
            print(f"     [ERR] Failed to parse place: {e}")
            
    return results

def process_and_commit_places(db, places, district: str, category_name: str, normalized_category: str, live: bool):
    """Processes extracted places and writes them immediately to the DB."""
    if not places:
        return
        
    print(f"  -> Merging {len(places)} listings into Supabase...")
    inserted_count = 0
    updated_count = 0
    
    for h in places:
        # Check by exact Google Maps URL first
        existing = db.query(models.Listing).filter(models.Listing.jd_url == h["place_url"]).first()
        
        # Or check by name + district coordinates fuzzy match
        if not existing and h["latitude"] and h["longitude"]:
            existing = db.query(models.Listing).filter(
                models.Listing.category == category_name,
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
            if h["menu_url"]:
                new_amenities.append(("Menu Link", h["menu_url"]))
            for svc in h.get("service_attrs", []):
                new_amenities.append(("Service", svc))
                
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
            
            # Update menu items if existing listing has no menu items
            if h.get("menu_items") and live:
                has_menu = db.query(models.MenuItem).filter(models.MenuItem.listing_id == existing.id).first()
                if not has_menu:
                    for m in h["menu_items"]:
                        db.add(models.MenuItem(
                            listing_id=existing.id,
                            name=m["name"],
                            price=m["price"],
                            is_veg=m["is_veg"]
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
                    category=category_name,
                    subcategory=h["subcategory"],
                    normalized_category=normalized_category,
                    opening_hours="24 Hours" if category_name.lower() == "hospitals" else "Regular Hours",
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
                if h["menu_url"]:
                    amenities_to_add.append(("Menu Link", h["menu_url"]))
                for svc in h.get("service_attrs", []):
                    amenities_to_add.append(("Service", svc))
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
                        
                # Add menu items to menu_items
                if h.get("menu_items"):
                    for m in h["menu_items"]:
                        db.add(models.MenuItem(
                            listing_id=new_listing.id,
                            name=m["name"],
                            price=m["price"],
                            is_veg=m["is_veg"]
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
    parser.add_argument("--query", required=True, help="Search query keyword (e.g. restaurants, cafes)")
    parser.add_argument("--category", required=True, help="Category field in DB (e.g. Restaurants)")
    parser.add_argument("--normalized-category", required=True, help="Normalized category field in DB (e.g. Food & Restaurants)")
    parser.add_argument("--limit-pins", type=int, default=None, help="Limit number of pincodes to scrape")
    parser.add_argument("--max-photos", type=int, default=1, help="Max photos to extract per place (default: 1)")
    parser.add_argument("--live", action="store_true", help="Write changes directly to database")
    parser.add_argument("--start-pin-index", type=int, default=0, help="Pincode index to start scraping from (0-based)")
    args = parser.parse_args()
    
    db = SessionLocal()
    
    print("=" * 60)
    print("GOOGLE MAPS KERALA GENERAL SCRAPER")
    print("=" * 60)
    print(f"District: {args.district}")
    print(f"Query: {args.query}")
    print(f"Category: {args.category}")
    print(f"Normalized Category: {args.normalized_category}")
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
    if args.start_pin_index > 0:
        pincodes = pincodes[args.start_pin_index:]
        print(f"Starting search from pincode index {args.start_pin_index} (Pincode {args.start_pin_index + 1}).")
    if args.limit_pins:
        pincodes = pincodes[:args.limit_pins]
        print(f"Limiting search to first {len(pincodes)} pincodes.")
    
    # Auto-detect already-scraped pincodes from DB
    scraped_pincodes = set()
    try:
        rows = db.query(models.Listing.address).filter(
            models.Listing.category == args.category,
            models.Listing.district == args.district
        ).all()
        for (addr,) in rows:
            if addr:
                # Extract 6-digit pincode from address string
                pin_match = re.search(r'\b(\d{6})\b', addr)
                if pin_match:
                    scraped_pincodes.add(pin_match.group(1))
        print(f"Found {len(scraped_pincodes)} pincodes already scraped in DB for {args.category}/{args.district}.")
    except Exception as e:
        print(f"[WARN] Could not check scraped pincodes: {e}")
    
    # Also check progress file for crash recovery
    progress_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f".scraper_progress_{args.district}_{args.category}.json")
    last_completed_index = -1
    try:
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                progress = json.load(f)
                last_completed_index = progress.get('last_completed_index', -1)
                last_pin = progress.get('last_pincode', '')
                print(f"Progress file found: last completed pincode index {last_completed_index} ({last_pin})")
    except Exception:
        pass
    
    # Initialize Playwright browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Always use Desktop Viewport to scrape listings, photos, names, and ratings reliably
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            viewport={"width": 1400, "height": 900}
        )
        page = await context.new_page()
        
        processed_urls = set()
        skipped_count = 0
        for index, pin in enumerate(pincodes):
            # Skip if pincode already scraped in DB
            if pin in scraped_pincodes:
                skipped_count += 1
                print(f"\n--- Pincode {index+1}/{len(pincodes)}: {pin} --- SKIPPED (already in DB)")
                continue
            
            # Skip if before last completed index (crash recovery)
            if index <= last_completed_index:
                skipped_count += 1
                print(f"\n--- Pincode {index+1}/{len(pincodes)}: {pin} --- SKIPPED (progress file)")
                continue
                
            if skipped_count > 0 and index == skipped_count:
                print(f"\n>>> Skipped {skipped_count} already-scraped pincodes. Resuming from pincode {pin}...")
            
            print(f"\n--- Pincode {index+1}/{len(pincodes)}: {pin} ---")
            places = await scrape_pincode_places(browser, page, pin, query=args.query, max_photos=args.max_photos, category_name=args.category, db=db, processed_urls=processed_urls)
            if places:
                process_and_commit_places(
                    db, places, 
                    district=args.district, 
                    category_name=args.category, 
                    normalized_category=args.normalized_category, 
                    live=args.live
                )
            
            # Save progress after each pincode
            try:
                with open(progress_file, 'w') as f:
                    json.dump({'last_completed_index': index, 'last_pincode': pin}, f)
            except Exception:
                pass
            
        await browser.close()
        
    # Clean up progress file on successful completion
    try:
        if os.path.exists(progress_file):
            os.remove(progress_file)
    except Exception:
        pass
    
    print(f"\nScraping complete! Skipped {skipped_count} already-scraped pincodes.")
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
