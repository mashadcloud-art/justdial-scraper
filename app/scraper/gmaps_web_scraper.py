"""
Google Maps Web Scraper (Desktop Playwright)
=============================================
Scrapes business listings from Google Maps using a real browser.
Completely independent of the JustDial scraper — does NOT touch any existing files.

Extracts per listing:
  - Business name
  - Phone number
  - Address
  - Website
  - Rating + review count
  - Opening hours
  - Category
  - Latitude / Longitude (from Maps URL)
  - Photos (all categories)
  - Menu photos (tagged separately)

Uploads to existing /api/v1/upload-listing endpoint.
"""

import json
import os
import re
import time
import requests
from typing import List, Dict, Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

try:
    from playwright_stealth import stealth_sync as stealth
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

try:
    from app.scraper.logger import log
except ImportError:
    def log(msg: str, ok: bool = True):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
API_UPLOAD_URL = os.getenv("API_UPLOAD_URL", "http://localhost:8000/api/v1/upload-listing")

# Delay between listing scrapes (seconds) — keep this to avoid blocks
DELAY_BETWEEN_LISTINGS = 6
DELAY_BETWEEN_SCROLLS  = 2
MAX_PHOTO_SCROLL       = 15  # how many times to scroll the photo panel (increased for more images)


# ─────────────────────────────────────────
# BROWSER SETUP
# ─────────────────────────────────────────
def _build_browser(playwright):
    """Launch a stealth Chromium browser."""
    browser = playwright.chromium.launch(
        headless=False,   # visible window — less likely to be flagged
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
        ]
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
        locale="en-US",
    )
    page = context.new_page()
    if STEALTH_AVAILABLE:
        stealth(page)
    return browser, context, page


# ─────────────────────────────────────────
# COORDINATES FROM URL
# ─────────────────────────────────────────
def _extract_coords_from_url(url: str) -> tuple:
    """Extract lat/lng from a Google Maps URL like .../@12.345,76.543,..."""
    m = re.search(r"@([-\d.]+),([-\d.]+)", url)
    if m:
        return m.group(1), m.group(2)
    return "", ""


# ─────────────────────────────────────────
# DETAIL PAGE SCRAPER
# ─────────────────────────────────────────
def _scrape_listing_details(page: Page) -> Dict:
    """
    Scrape all details from an open Google Maps listing page.
    Returns a dict with name, phone, address, website, rating,
    reviews, hours, category, latitude, longitude.
    """
    result = {
        "name": "", "phone": "", "address": "", "website": "",
        "rating": "", "reviews": "", "hours": "", "category": "",
        "latitude": "", "longitude": "",
    }

    try:
        # Wait for the main info panel to load
        page.wait_for_selector("h1.DUwDvf, h1[class*='fontHeadlineLarge']", timeout=10000)
    except PlaywrightTimeout:
        log("  ⚠️ Detail panel did not load in time", ok=False)
        return result

    # ── Name ──
    try:
        result["name"] = page.locator("h1.DUwDvf, h1[class*='fontHeadlineLarge']").first.inner_text().strip()
    except Exception:
        pass

    # ── Category (subtitle below name) ──
    try:
        result["category"] = page.locator("button.DkEaL, [class*='fontBodyMedium'] button").first.inner_text().strip()
    except Exception:
        pass

    # ── Rating ──
    try:
        rating_el = page.locator("div.F7nice span[aria-hidden='true']").first
        result["rating"] = rating_el.inner_text().strip()
    except Exception:
        pass

    # ── Reviews count ──
    try:
        reviews_el = page.locator("div.F7nice span[aria-label*='review']").first
        aria = reviews_el.get_attribute("aria-label") or ""
        m = re.search(r"([\d,]+)", aria)
        if m:
            result["reviews"] = m.group(1).replace(",", "")
    except Exception:
        pass

    # ── Address ──
    try:
        addr_btn = page.locator("button[data-item-id='address'], [data-tooltip='Copy address']").first
        result["address"] = addr_btn.inner_text().strip()
    except Exception:
        # Fallback: look for address-like text near the copy icon
        try:
            result["address"] = page.locator("[aria-label*='Address']").first.get_attribute("aria-label", timeout=3000) or ""
            result["address"] = result["address"].replace("Address: ", "").strip()
        except Exception:
            pass

    # ── Phone ──
    try:
        phone_btn = page.locator(
            "button[data-item-id*='phone'], [data-tooltip='Copy phone number'], [aria-label*='phone']"
        ).first
        raw = phone_btn.inner_text().strip()
        # Clean to digits only for storage
        result["phone"] = raw
    except Exception:
        try:
            result["phone"] = page.locator("[aria-label*='Phone']").first.get_attribute("aria-label", timeout=3000) or ""
            result["phone"] = result["phone"].replace("Phone: ", "").strip()
        except Exception:
            pass

    # ── Website ──
    try:
        web_btn = page.locator(
            "a[data-item-id='authority'], a[aria-label*='website'], a[data-tooltip='Open website']"
        ).first
        result["website"] = web_btn.get_attribute("href") or ""
    except Exception:
        pass

    # ── Opening hours ──
    try:
        # Click "See more hours" button if present to expand
        try:
            page.locator("button[aria-label*='hour'], [data-item-id*='oh']").first.click(timeout=2000)
            time.sleep(0.5)
        except Exception:
            pass
        hours_el = page.locator("[aria-label*='hour']").first
        result["hours"] = hours_el.get_attribute("aria-label") or ""
        result["hours"] = result["hours"].replace("Hours", "").strip(". ")
    except Exception:
        pass

    # ── Coordinates from URL ──
    result["latitude"], result["longitude"] = _extract_coords_from_url(page.url)

    return result


# ─────────────────────────────────────────
# PHOTO SCRAPER
# ─────────────────────────────────────────
def _scrape_photos(page: Page) -> List[Dict]:
    """
    Open the photo panel for the current listing and collect image URLs.
    Returns list of {"url": ..., "category": "general"|"menu"}.
    """
    photos = []
    seen_canonical = set()

    def _canonical(url: str) -> str:
        """Strip resolution params to get a stable image identity."""
        return re.sub(r"=(w\d+|h\d+|s\d+|w\d+-h\d+[^&]*).*$", "", url)

    def _collect_all_imgs(category: str):
        """Collect every Google image URL currently in the DOM (img src + data-src + srcset + background)."""
        try:
            raw_urls = page.evaluate("""
                () => {
                    let urls = [];
                    // img tags with src / data-src
                    document.querySelectorAll('img, [data-src]').forEach(el => {
                        let s = el.getAttribute('data-src') || el.src || el.getAttribute('src') || '';
                        if (s && (s.includes('googleusercontent') || s.includes('ggpht') || s.includes('lh3.google') || s.includes('gps-cs-s'))) {
                            urls.push(s);
                        }
                        // srcset
                        let ss = el.getAttribute('srcset') || '';
                        ss.split(',').forEach(part => {
                            let u = part.trim().split(' ')[0];
                            if (u && (u.includes('googleusercontent') || u.includes('ggpht') || u.includes('lh3.google'))) urls.push(u);
                        });
                    });
                    // background-image styles
                    document.querySelectorAll('[style*="googleusercontent"], [style*="ggpht"], [style*="lh3.google"]').forEach(el => {
                        let style = el.getAttribute('style') || '';
                        let matches = Array.from(style.matchAll(/url\("?([^"')]+(?:googleusercontent|ggpht|lh3\.google)[^"')]+)"?\)/g));
                        matches.forEach(m => urls.push(m[1]));
                    });
                    return urls;
                }
            """)
            tiny_sz = ['w32-h32', 'w48-h48', 'w64-h64', 'w20-h20', 'w34-h34', 'w16-h16', 'w24-h24', 'w40-h40']
            for src in raw_urls:
                if any(sz in src for sz in tiny_sz):
                    continue
                if '/a/' in src or '/a-/' in src:   # user avatar
                    continue
                base = _canonical(src)
                if base not in seen_canonical:
                    seen_canonical.add(base)
                    high_res = base + "=w1200-h900"
                    photos.append({"url": high_res, "category": category})
        except Exception:
            pass

    def _scroll_gallery():
        """Scroll every scrollable container that has Google images (mirrors proven approach)."""
        try:
            page.evaluate("""
                () => {
                    let divs = Array.from(document.querySelectorAll('div'));
                    for (let d of divs) {
                        let style = window.getComputedStyle(d);
                        if ((style.overflowY === 'auto' || style.overflowY === 'scroll')
                            && d.scrollHeight > d.clientHeight + 50) {
                            let imgs = d.querySelectorAll('img, [data-src]');
                            let hasGmaps = false;
                            for (let img of imgs) {
                                let s = img.src || img.getAttribute('data-src') || '';
                                if (s.includes('googleusercontent') || s.includes('ggpht') || s.includes('lh3.google')) {
                                    hasGmaps = true;
                                    break;
                                }
                            }
                            if (hasGmaps || imgs.length > 5) {
                                d.scrollTop = d.scrollHeight;
                            }
                        }
                    }
                    window.scrollBy(0, 1500);
                }
            """)
        except Exception:
            pass

    # ── Step 1: Try to open the photo gallery ──
    gallery_opened = False
    open_selectors = [
        "button[jsaction*='heroHeaderImage']",
        "div[jsaction*='heroHeaderImage']",
        "button[aria-label*='photo' i]",
        "button[aria-label*='Photo']",
        "button[jsaction*='pane.photo']",
        "a[jsaction*='pane.photo']",
        "button.aoRNLd",
        "div.RZ66Rb",
        "div.b0cq8c",
        "[class*='gallery'] button",
        "div[jsaction*='openPhoto']",
    ]
    for sel in open_selectors:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0:
                btn.click(timeout=3000)
                time.sleep(2.5)
                gallery_opened = True
                log("  🖼️ Photo gallery opened.")
                break
        except Exception:
            pass

    if not gallery_opened:
        log("  ⚠️ Could not open photo gallery — collecting hero images only.", ok=False)
        _collect_all_imgs("general")
        log(f"  📸 Total photos collected: {len(photos)}")
        return photos

    # ── Step 2: Try to select a cleaner gallery tab (By owner, Exterior, Interior) ──
    log("  📷 Checking for cleaner gallery tabs...")
    tab_clicked = False
    cleaner_labels = [("By owner", "general"), ("Owner", "general"), ("Exterior", "general"), ("Interior", "general")]
    for tab_label, cat in cleaner_labels:
        try:
            tab = page.locator(
                f'button[aria-label*="{tab_label}" i], div[role="tab"]:has-text("{tab_label}")'
            ).first
            if tab.count() > 0 and tab.is_visible(timeout=1000):
                log(f"  🎯 Found cleaner tab '{tab_label}'. Clicking it to filter out selfies...")
                tab.click(timeout=3000)
                time.sleep(2)
                tab_clicked = True
                break
        except Exception:
            pass

    if not tab_clicked:
        try:
            # Fallback evaluate selector
            tab_clicked = page.evaluate("""
                () => {
                    const labels = ["by owner", "owner", "exterior", "interior"];
                    const buttons = Array.from(document.querySelectorAll('button, div[role="tab"], div[role="radio"], span'));
                    for (let label of labels) {
                        for (let btn of buttons) {
                            const txt = (btn.innerText || btn.textContent || "").toLowerCase().trim();
                            if (txt === label || txt.includes(label)) {
                                btn.click();
                                return true;
                            }
                        }
                    }
                    return false;
                }
            """)
            if tab_clicked:
                log("  🎯 Clicked cleaner tab using DOM selector.")
                time.sleep(2)
        except Exception as e:
            log(f"  [WARN] Failed to click cleaner tab: {e}")

    # ── Step 3: Scroll and collect from the active tab ──
    log("  📷 Scrolling gallery for photos...")
    prev_count = 0
    stale = 0
    for _ in range(MAX_PHOTO_SCROLL):
        _scroll_gallery()
        time.sleep(0.8)
        _collect_all_imgs("general")
        if len(photos) == prev_count:
            stale += 1
            if stale >= 4:
                break
        else:
            stale = 0
            prev_count = len(photos)

    # ── Step 4: Try 'Menu' or 'Food' if relevant ──
    for tab_label, cat in [("Menu", "menu"), ("Food", "food")]:
        try:
            tab = page.locator(
                f'button[aria-label*="{tab_label}" i], div[role="tab"]:has-text("{tab_label}")'
            ).first
            if tab.count() > 0 and tab.is_visible(timeout=1000):
                tab.click(timeout=3000)
                time.sleep(1.5)
                for _ in range(6):
                    _scroll_gallery()
                    time.sleep(0.6)
                _collect_all_imgs(cat)
                log(f"  📷 '{tab_label}' tab: {len(photos)} total photos")
        except Exception:
            pass

    log(f"  📸 Total photos collected: {len(photos)}")
    return photos


# ─────────────────────────────────────────
# UPLOAD TO LOCAL API
# ─────────────────────────────────────────
def _upload_listing(listing: Dict, photos: List[Dict], district: str) -> bool:
    """Upload scraped data to the existing /api/v1/upload-listing endpoint."""
    image_urls = [{"path": p["url"], "category": p["category"]} for p in photos]

    data = {
        "name":          listing["name"],
        "phone":         listing.get("phone", ""),
        "address":       listing.get("address", ""),
        "source_url":    listing.get("website") or f"https://maps.google.com/?q={listing['name'].replace(' ', '+')}",
        "category":      listing.get("category", ""),
        "opening_hours": listing.get("hours", ""),
        "district":      district,
        "latitude":      listing.get("latitude", ""),
        "longitude":     listing.get("longitude", ""),
        "image_urls_json": json.dumps(image_urls) if image_urls else None,
    }

    # Remove None values
    data = {k: v for k, v in data.items() if v is not None}

    try:
        resp = requests.post(API_UPLOAD_URL, data=data, timeout=15)
        return resp.status_code in (200, 201)
    except Exception as e:
        log(f"  ❌ Upload error: {e}", ok=False)
        return False


# ─────────────────────────────────────────
# SEARCH RESULTS LIST SCRAPER
# ─────────────────────────────────────────
def _get_listing_links(page: Page, query: str, max_results: int) -> List[str]:
    """
    Search Google Maps for a query and collect listing URLs from the results panel.
    Returns a list of place URLs.
    """
    search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}/"
    log(f"🔍 Searching: {search_url}")
    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(4)

    links = []
    seen = set()

    def _harvest():
        """Collect all currently visible listing links."""
        anchors = page.locator("a[href*='/maps/place/']").all()
        for a in anchors:
            href = a.get_attribute("href") or ""
            # Normalize: strip after the place name section
            m = re.match(r"(https://www\.google\.com/maps/place/[^/]+/)", href)
            if m:
                url = m.group(1)
            elif "/maps/place/" in href:
                url = href.split("?")[0]
            else:
                continue
            if url not in seen:
                seen.add(url)
                links.append(url)

    # Scroll the results panel to load more listings
    scroll_attempts = 0
    max_scrolls = max(10, max_results // 5)

    while len(links) < max_results and scroll_attempts < max_scrolls:
        _harvest()
        log(f"  Found {len(links)} listings so far (scroll {scroll_attempts + 1}/{max_scrolls})...")

        if len(links) >= max_results:
            break

        # Scroll inside the results panel (left sidebar)
        try:
            panel = page.locator("div[role='feed'], div[aria-label*='Results']").first
            panel.evaluate("el => el.scrollBy(0, 1000)")
        except Exception:
            page.evaluate("window.scrollBy(0, 1000)")

        time.sleep(DELAY_BETWEEN_SCROLLS)

        # Check if "You've reached the end of the list"
        try:
            end_msg = page.locator("span:has-text('end of the list'), p:has-text('No more results')").first
            if end_msg.is_visible(timeout=500):
                log("  📋 Reached end of results list.")
                break
        except Exception:
            pass

        scroll_attempts += 1

    _harvest()
    result = links[:max_results]
    log(f"✅ Collected {len(result)} listing URLs.")
    return result


# ─────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────
def scrape_gmaps_web(
    query: str,
    district: str = "",
    max_results: int = 20,
    scrape_photos: bool = True,
    upload: bool = True,
) -> Dict:
    """
    Main entry point for Google Maps web scraper.

    Args:
        query:         Search query e.g. "restaurants in Kannur"
        district:      District name for DB tagging
        max_results:   Max number of listings to scrape
        scrape_photos: Whether to scrape photos (slower but richer)
        upload:        Whether to upload results to local API

    Returns:
        {"query": ..., "results": [...], "uploaded": N}
    """
    log(f"🗺️ Google Maps Web Scraper starting: '{query}'")
    output = {"query": query, "results": [], "uploaded": 0}

    with sync_playwright() as p:
        browser, context, page = _build_browser(p)

        try:
            # ── Step 1: Collect listing URLs from search results ──
            listing_urls = _get_listing_links(page, query, max_results)

            if not listing_urls:
                log("⚠️ No listings found. Google may have shown a CAPTCHA.", ok=False)
                return output

            # ── Step 2: Visit each listing ──
            for idx, url in enumerate(listing_urls):
                log(f"\n[{idx + 1}/{len(listing_urls)}] Opening: {url}")

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(3)
                except Exception as e:
                    log(f"  ❌ Failed to load listing: {e}", ok=False)
                    continue

                # ── Step 3: Scrape details ──
                details = _scrape_listing_details(page)

                if not details["name"]:
                    log("  ⚠️ Could not extract name, skipping.", ok=False)
                    continue

                log(f"  ✅ Name    : {details['name']}")
                log(f"  📞 Phone   : {details['phone'] or 'N/A'}")
                log(f"  📍 Address : {details['address'] or 'N/A'}")
                log(f"  ⭐ Rating  : {details['rating'] or 'N/A'} ({details['reviews'] or '0'} reviews)")
                log(f"  🕐 Hours   : {details['hours'] or 'N/A'}")
                log(f"  🌐 Website : {details['website'] or 'N/A'}")
                log(f"  🏷️ Category: {details['category'] or 'N/A'}")
                log(f"  🌍 Coords  : {details['latitude']}, {details['longitude']}")

                # ── Step 4: Scrape photos ──
                photos = []
                if scrape_photos:
                    try:
                        photos = _scrape_photos(page)
                    except Exception as e:
                        log(f"  ⚠️ Photo scrape failed: {e}", ok=False)

                details["photos"] = photos
                details["listing_url"] = url
                output["results"].append(details)

                # ── Step 5: Upload ──
                if upload and details["name"]:
                    success = _upload_listing(details, photos, district)
                    if success:
                        output["uploaded"] += 1
                        log(f"  💾 Uploaded to DB ✅")
                    else:
                        log(f"  ⚠️ Upload failed", ok=False)

                # Check stop flag (set by /api/v1/gmaps-web/stop)
                stop_flag = os.path.join(
                    os.path.dirname(__file__), "..", "..", "data", "gmaps_web_stop.flag"
                )
                if os.path.exists(stop_flag):
                    try:
                        os.remove(stop_flag)
                    except Exception:
                        pass
                    log("🛑 Stop flag detected — stopping scraper.")
                    break

                # Polite delay between listings to avoid blocks
                time.sleep(DELAY_BETWEEN_LISTINGS)

        except Exception as e:
            log(f"❌ Scraper error: {e}", ok=False)
        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass

    log(f"\n🏁 Done. {len(output['results'])} scraped, {output['uploaded']} uploaded.")
    return output


# ─────────────────────────────────────────
# SAVE RESULTS TO JSON
# ─────────────────────────────────────────
def save_results(data: Dict, output_path: str = None) -> str:
    """Save scrape results to a JSON file."""
    if not output_path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9]", "_", data["query"].lower())[:30]
        output_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "data",
            f"gmaps_web_{slug}_{ts}.json"
        )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"💾 Results saved to: {output_path}")
    return output_path


# ─────────────────────────────────────────
# CLI
# ─────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Google Maps Web Scraper")
    parser.add_argument("query",    help='e.g. "restaurants in Kannur"')
    parser.add_argument("--max",    type=int, default=20,    help="Max listings")
    parser.add_argument("--district", default="",            help="District tag for DB")
    parser.add_argument("--no-photos",  action="store_true", help="Skip photo scraping")
    parser.add_argument("--no-upload",  action="store_true", help="Don't upload to DB")
    args = parser.parse_args()

    results = scrape_gmaps_web(
        query=args.query,
        district=args.district,
        max_results=args.max,
        scrape_photos=not args.no_photos,
        upload=not args.no_upload,
    )
    save_results(results)
    print(json.dumps(results, ensure_ascii=False, indent=2))
