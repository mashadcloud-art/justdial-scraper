import sys
import os
import asyncio
import re
import argparse

# Add parent directory to path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import joinedload
from app.database import SessionLocal
from app import models
from playwright.async_api import async_playwright

async def scrape_gallery_images(page, max_photos=50):
    image_urls = set()
    
    try:
        # Click the hero image to open the gallery
        open_selectors = [
            "button[jsaction*='heroHeaderImage']",
            "div[jsaction*='heroHeaderImage']",
            "button.aoRNLd",
            "div.RZ66Rb",
            "button[aria-label*='photo' i]",
            "button[jsaction*='pane.photo']",
            "a[jsaction*='pane.photo']",
        ]
        
        gallery_opened = False
        for sel in open_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(4000)
                    gallery_opened = True
                    break
            except Exception:
                pass
                
        if not gallery_opened:
            print("    [WARN] Could not find gallery button.")
            return []
            
        # Aggressive scrolling to load images
        stale_rounds = 0
        prev_img_count = 0
        
        for scroll_round in range(40):
            try:
                scrolled = await page.evaluate("""
                    () => {
                        let didScroll = false;
                        let divs = Array.from(document.querySelectorAll('div'));
                        for (let d of divs) {
                            let style = window.getComputedStyle(d);
                            if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && d.scrollHeight > d.clientHeight + 50) {
                                let imgs = d.querySelectorAll('img, [data-src]');
                                let hasGmaps = false;
                                for (let img of imgs) {
                                    let s = img.src || img.getAttribute('data-src') || img.getAttribute('src') || '';
                                    if (s.includes('googleusercontent') || s.includes('ggpht')) {
                                        hasGmaps = true;
                                        break;
                                    }
                                }
                                if (hasGmaps || imgs.length > 5) {
                                    d.scrollTop = d.scrollHeight;
                                    didScroll = true;
                                }
                            }
                        }
                        if (!didScroll) {
                            window.scrollBy(0, 1500);
                        }
                        return didScroll;
                    }
                """)
                await page.wait_for_timeout(600)
                
                cur_img_count = await page.evaluate("""
                    () => {
                        let count = 0;
                        document.querySelectorAll('img, [data-src]').forEach(function(el) {
                            let s = el.getAttribute('data-src') || el.src || el.getAttribute('src') || '';
                            if (s && (s.includes('googleusercontent') || s.includes('ggpht'))
                                && !s.includes('w32-h32') && !s.includes('w48-h48')
                                && !s.includes('w64-h64') && !s.includes('w20-h20')) {
                                count++;
                            }
                        });
                        document.querySelectorAll('[style*="googleusercontent"], [style*="ggpht"]').forEach(function(el) {
                            let style = el.getAttribute('style') || '';
                            if (!style.includes('w32-h32') && !style.includes('w48-h48') && !style.includes('w64-h64') && !style.includes('w20-h20')) {
                                count++;
                            }
                        });
                        return count;
                    }
                """)
                
                if cur_img_count == prev_img_count:
                    stale_rounds += 1
                    if stale_rounds >= 6:
                        break
                else:
                    stale_rounds = 0
                    prev_img_count = cur_img_count
                    
            except Exception:
                break
                
        # Extract all image URLs
        all_imgs = await page.evaluate("""
            () => {
                let results = [];
                document.querySelectorAll('img, [data-src]').forEach(function(el) {
                    let s = el.getAttribute('data-src') || el.src || el.getAttribute('src') || '';
                    if (s && (s.includes('googleusercontent') || s.includes('ggpht'))) {
                        results.push(s);
                    }
                });
                document.querySelectorAll('[style*="googleusercontent"], [style*="ggpht"]').forEach(function(el) {
                    let style = el.getAttribute('style') || '';
                    try {
                        let matches = Array.from(style.matchAll(/url\\(['"]?(.*?)['"]?\\)/g));
                        for (let m of matches) {
                            let url = m[1];
                            if (url && (url.includes('googleusercontent') || url.includes('ggpht'))) {
                                results.push(url);
                            }
                        }
                    } catch(e) {}
                });
                return results;
            }
        """)
        
        # Deduplicate and canonicalize
        for src in all_imgs:
            if len(image_urls) >= max_photos:
                break
            # Skip tiny thumbnails and avatars
            if any(sz in src for sz in ['w32-h32', 'w48-h48', 'w64-h64', 'w20-h20', '/a/']):
                continue
                
            base = re.sub(r"=(w\d+|h\d+|s\d+|w\d+-h\d+).*$", "", src)
            large_url = base + "=w1200-h900"
            image_urls.add(large_url)
            
    except Exception as e:
        print(f"    [ERR] Error during gallery extraction: {e}")
        
    return list(image_urls)

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

async def main(target_category=None, target_district=None, no_shutdown=False):
    print("=" * 60)
    print("GOOGLE MAPS BACKGROUND DEEP IMAGE SCRAPER (DAEMON MODE)")
    if target_category:
        print(f"Targeting only category: '{target_category}'")
    if target_district:
        print(f"Targeting only district: '{target_district}'")
    print("=" * 60)
    if no_shutdown:
        print("Running continuously (24/7 Mode). Will never auto-shutdown.")
    else:
        print("Running continuously. Will auto-shutdown after 2 minutes of no new listings...")
    
    db = SessionLocal()
    idle_time = 0
    check_interval = 10 # seconds
    max_idle_time = 120 # 2 minutes
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            viewport={"width": 1400, "height": 900}
        )
        page = await context.new_page()
        
        while True:
            query = db.query(models.Listing).filter(
                models.Listing.jd_url != None,
                models.Listing.jd_url.like("%google.com/maps%")
            )
            
            if target_category:
                if target_category.lower() == "restaurants":
                    query = query.filter(
                        (models.Listing.category.ilike("%restaurant%")) | 
                        (models.Listing.category.ilike("%cafe%")) | 
                        (models.Listing.category.ilike("%food%")) |
                        (models.Listing.normalized_category.ilike("%restaurant%")) |
                        (models.Listing.normalized_category.ilike("%food%"))
                    )
                else:
                    query = query.filter(
                        (models.Listing.category == target_category) |
                        (models.Listing.normalized_category == target_category)
                    )
                
            if target_district:
                query = query.filter(models.Listing.district.ilike(f"%{target_district}%"))
                
            # Query IDs first to avoid keeping model instances open and detached
            listings = query.all()
            target_ids = [L.id for L in listings if len(L.images) < 20]
            
            if not target_ids:
                if not no_shutdown:
                    idle_time += check_interval
                    if idle_time >= max_idle_time:
                        print(f"No new listings for {max_idle_time} seconds. Shutting down daemon...")
                        break
                else:
                    # Log sleeping status occasionally in 24/7 Mode
                    if idle_time % 60 == 0:
                        print("  [24/7 Daemon] Queue empty. Sleeping for 10s...")
                    idle_time += check_interval
                await asyncio.sleep(check_interval)
                continue
                
            idle_time = 0 # reset idle time
            print(f"Found {len(target_ids)} listings that need deep image scraping.")
            
            for idx, listing_id_val in enumerate(target_ids):
                # Fetch listing inside a fresh session for this iteration
                db_iter = SessionLocal()
                listing = db_iter.query(models.Listing).options(joinedload(models.Listing.images)).filter_by(id=listing_id_val).first()
                if not listing:
                    db_iter.close()
                    continue
                
                # Check if someone else updated it in the meantime
                if len(listing.images) >= 20:
                    db_iter.close()
                    continue

                listing_name_val = listing.name
                try:
                    print(f"\n[{idx+1}/{len(target_ids)}] Processing {listing_name_val}...")
                except Exception:
                    safe_name = listing_name_val.encode('ascii', 'ignore').decode('ascii')
                    print(f"\n[{idx+1}/{len(target_ids)}] Processing {safe_name}...")
                
                url = listing.jd_url + "&hl=en" if "?" in listing.jd_url else listing.jd_url + "?hl=en"
                
                try:
                    await page.goto(url, wait_until="commit", timeout=60000)
                    await page.wait_for_timeout(3000) # Let UI settle
                    
                    await page.wait_for_selector("h1.DUwDvf", timeout=10000)
                    
                    print("  -> Scraping gallery...")
                    new_image_urls = await scrape_gallery_images(page, max_photos=50)
                    
                    try:
                        if new_image_urls:
                            print(f"  -> Extracted {len(new_image_urls)} new images! Saving to DB...")
                            existing_urls = {img.image_path for img in listing.images}
                            
                            for img_url in new_image_urls:
                                if img_url not in existing_urls:
                                    db_iter.add(models.ListingImage(
                                        listing_id=listing_id_val,
                                        image_path=img_url,
                                        category="general",
                                        is_primary=False
                                    ))
                                    existing_urls.add(img_url)
                                    
                            db_iter.commit()
                            print("  -> Saved!")
                        else:
                            print("  -> No new images found.")
                            # To prevent infinite loop if a place really has 0 photos, we add a dummy image so count > 1
                            db_iter.add(models.ListingImage(
                                listing_id=listing_id_val,
                                        image_path="NO_IMAGES_FOUND_FLAG",
                                        category="system",
                                        is_primary=False
                                    ))
                            db_iter.commit()
                            print("  -> Saved!")
                    except Exception as db_err:
                        print(f"  -> [DB ERROR] Commit failed: {db_err}")
                        try:
                            db_iter.rollback()
                        except:
                            pass

                    # Extract digital menu in background if it is a Restaurant
                    is_restaurant = listing.category and "restaurant" in listing.category.lower()
                    if is_restaurant:
                        has_menu = db_iter.query(models.MenuItem).filter_by(listing_id=listing_id_val).first() is not None
                        if not has_menu:
                            print("  -> Scraping digital menu...")
                            menu_items = await extract_gmaps_menu(browser, url)
                            if menu_items:
                                print(f"  -> Extracted {len(menu_items)} menu items! Saving to DB...")
                                for m in menu_items:
                                    db_iter.add(models.MenuItem(
                                        listing_id=listing_id_val,
                                        name=m["name"],
                                        price=m["price"],
                                        is_veg=m["is_veg"]
                                    ))
                                db_iter.commit()
                                print("  -> Saved menus!")
                            else:
                                print("  -> No digital menu found.")
                        
                except Exception as e:
                    try:
                        print(f"  -> [CRASH] Error parsing {listing_name_val}: {e}")
                    except Exception:
                        safe_name = listing_name_val.encode('ascii', 'ignore').decode('ascii')
                        print(f"  -> [CRASH] Error parsing {safe_name}: {e}")
                    try:
                        db_iter.rollback()
                    except:
                        pass
                    
                    try:
                        db_iter.add(models.ListingImage(listing_id=listing_id_val, image_path="CRASH_FLAG", category="system", is_primary=False))
                        db_iter.commit()
                        print("  -> Crash flag saved to DB.")
                    except Exception as db_err:
                        print(f"  -> [DB ERROR] Could not save crash flag: {db_err}")
                        try:
                            db_iter.rollback()
                        except:
                            pass
                    
                    try:
                        await page.close()
                        await context.close()
                        context = await browser.new_context(viewport={"width": 1400, "height": 900})
                        page = await context.new_page()
                    except:
                        pass
                finally:
                    db_iter.close()
        
        await browser.close()
        
    db.close()
    print("\nBackground scraping daemon finished completely!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Background Deep Image Scraper")
    parser.add_argument("--category", type=str, default=None, help="Target a specific category (e.g. 'Pharmacies')")
    parser.add_argument("--district", type=str, default=None, help="Target a specific district (e.g. 'Kasaragod')")
    parser.add_argument("--no-shutdown", action="store_true", help="Run indefinitely and never auto-shutdown")
    args = parser.parse_args()
    
    # Store no_shutdown configuration globally or pass it into main
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(target_category=args.category, target_district=args.district, no_shutdown=args.no_shutdown))
