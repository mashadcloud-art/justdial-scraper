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
                        let imgs = Array.from(document.querySelectorAll('img, [data-src]'));
                        let count = 0;
                        for (let i of imgs) {
                            let s = i.src || i.getAttribute('data-src') || i.getAttribute('src') || '';
                            if ((s.includes('googleusercontent') || s.includes('ggpht'))
                                && !s.includes('w32-h32') && !s.includes('w48-h48')
                                && !s.includes('w64-h64') && !s.includes('w20-h20')) {
                                count++;
                            }
                        }
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

async def main(target_category=None, target_district=None):
    print("=" * 60)
    print("GOOGLE MAPS BACKGROUND DEEP IMAGE SCRAPER (DAEMON MODE)")
    if target_category:
        print(f"Targeting only category: '{target_category}'")
    if target_district:
        print(f"Targeting only district: '{target_district}'")
    print("=" * 60)
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
                query = query.filter(models.Listing.category == target_category)
                
            if target_district:
                query = query.filter(models.Listing.district.ilike(f"%{target_district}%"))
                
            listings = query.options(joinedload(models.Listing.images)).all()
            
            target_listings = [L for L in listings if len(L.images) <= 1]
            
            if not target_listings:
                idle_time += check_interval
                if idle_time >= max_idle_time:
                    print(f"No new listings for {max_idle_time} seconds. Shutting down daemon...")
                    break
                await asyncio.sleep(check_interval)
                continue
                
            idle_time = 0 # reset idle time
            print(f"Found {len(target_listings)} listings that need deep image scraping.")
            
            for idx, listing in enumerate(target_listings):
                listing_id_val = listing.id
                listing_name_val = listing.name
                print(f"\n[{idx+1}/{len(target_listings)}] Processing {listing_name_val}...")
                
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
                                    db.add(models.ListingImage(
                                        listing_id=listing_id_val,
                                        image_path=img_url,
                                        category="general",
                                        is_primary=False
                                    ))
                                    existing_urls.add(img_url)
                                    
                            db.commit()
                            print("  -> Saved!")
                        else:
                            print("  -> No new images found.")
                            # To prevent infinite loop if a place really has 0 photos, we add a dummy image so count > 1
                            db.add(models.ListingImage(
                                listing_id=listing_id_val,
                                image_path="NO_IMAGES_FOUND_FLAG",
                                category="system",
                                is_primary=False
                            ))
                            db.commit()
                            print("  -> Saved!")
                    except Exception as db_err:
                        print(f"  -> [DB ERROR] Commit failed: {db_err}")
                        try:
                            db.rollback()
                        except:
                            pass
                        try:
                            db.close()
                        except:
                            pass
                        db = SessionLocal()
                        
                except Exception as e:
                    print(f"  -> [CRASH] Error parsing {listing_name_val}: {e}")
                    try:
                        db.rollback()
                    except:
                        pass
                    
                    try:
                        # Re-open session in case of connection drop
                        db.close()
                        db = SessionLocal()
                        db.add(models.ListingImage(listing_id=listing_id_val, image_path="CRASH_FLAG", category="system", is_primary=False))
                        db.commit()
                        print("  -> Crash flag saved to DB.")
                    except Exception as db_err:
                        print(f"  -> [DB ERROR] Could not save crash flag: {db_err}")
                        try:
                            db.rollback()
                        except:
                            pass
                    
                    try:
                        await page.close()
                        await context.close()
                        context = await browser.new_context(viewport={"width": 1400, "height": 900})
                        page = await context.new_page()
                    except:
                        pass
        
        await browser.close()
        
    db.close()
    print("\nBackground scraping daemon finished completely!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Background Deep Image Scraper")
    parser.add_argument("--category", type=str, default=None, help="Target a specific category (e.g. 'Pharmacies')")
    parser.add_argument("--district", type=str, default=None, help="Target a specific district (e.g. 'Kasaragod')")
    args = parser.parse_args()
    
    asyncio.run(main(target_category=args.category, target_district=args.district))
