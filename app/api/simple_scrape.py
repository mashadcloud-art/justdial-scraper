"""
Simple one-shot Google Maps image scraper endpoint.
POST /api/v1/simple-scrape
Body: { "url": "https://www.google.com/maps/place/..." }
Returns immediately with scraped images.
"""
import re
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api/v1", tags=["simple_scrape"])


class SimpleScrapeRequest(BaseModel):
    url: str
    max_images: int = 30


class SimpleScrapeResponse(BaseModel):
    place_name: str
    image_urls: List[str]
    address: str = ""
    phone: str = ""
    rating: str = ""
    status: str


def canonical_img_url(url: str) -> str:
    return re.sub(r"=(w\d+|h\d+|s\d+|w\d+-h\d+).*$", "", url)


def is_valid_img(url: str) -> bool:
    if "/a/" in url or "/a-/" in url:
        return False
    bad_sizes = ["w32-h32", "w48-h48", "w64-h64", "w20-h20",
                 "w34-h34", "w16-h16", "w24-h24", "w40-h40", "w56-h56"]
    return not any(sz in url for sz in bad_sizes)


async def _do_scrape(url: str, max_images: int) -> dict:
    from playwright.async_api import async_playwright

    # Normalise URL: force English locale
    if "?" in url:
        nav_url = re.sub(r"hl=[a-z]{2}(-[A-Z]{2})?", "hl=en", url) if "hl=" in url else url + "&hl=en"
    else:
        nav_url = url + "?hl=en"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )

        await page.goto(nav_url, wait_until="commit", timeout=60000)

        # Wait for place name to load
        try:
            await page.wait_for_function(
                "() => { var el = document.querySelector('h1.DUwDvf'); return el && el.innerText.trim().length > 0; }",
                timeout=10000
            )
        except Exception:
            await page.wait_for_timeout(5000)

        await page.wait_for_timeout(1500)

        # -- Extract basic info --
        name_el = await page.query_selector("h1.DUwDvf")
        place_name = (await name_el.inner_text()).strip() if name_el else "Unknown"

        addr_el = await page.query_selector("button[data-item-id='address'] div.Io6YTe")
        address = (await addr_el.inner_text()).strip() if addr_el else ""

        phone = ""
        phone_el = await page.query_selector("button[data-item-id^='phone:tel:']")
        if phone_el:
            pid = await phone_el.get_attribute("data-item-id")
            phone = pid.replace("phone:tel:", "").strip()

        rating_el = await page.query_selector("div.F7nice > span > span[aria-hidden='true']")
        rating = (await rating_el.inner_text()).strip() if rating_el else ""

        # -- Open photo gallery --
        gallery_opened = False
        open_selectors = [
            "button[jsaction*='heroHeaderImage']",
            "div[jsaction*='heroHeaderImage']",
            "button.aoRNLd",
            "div.RZ66Rb",
            "button[aria-label*='photo' i]",
            "button[jsaction*='pane.photo']",
            "a[jsaction*='pane.photo']",
            "div.b0cq8c",
        ]
        for sel in open_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(3000)
                    gallery_opened = True
                    break
            except Exception:
                pass

        if gallery_opened:
            # Scroll to load images
            prev_count = 0
            stale = 0
            for _ in range(50):
                await page.evaluate("""
                    () => {
                        let divs = Array.from(document.querySelectorAll('div'));
                        let scrolled = false;
                        for (let d of divs) {
                            let s = window.getComputedStyle(d);
                            if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && d.scrollHeight > d.clientHeight + 50) {
                                let imgs = d.querySelectorAll('img,[data-src]');
                                for (let img of imgs) {
                                    let src = img.src || img.getAttribute('data-src') || '';
                                    if (src.includes('googleusercontent') || src.includes('ggpht')) {
                                        d.scrollTop = d.scrollHeight;
                                        scrolled = true;
                                        break;
                                    }
                                }
                            }
                        }
                        if (!scrolled) window.scrollBy(0, 1500);
                    }
                """)
                await page.wait_for_timeout(500)
                cur = await page.evaluate("""
                    () => {
                        let imgs = document.querySelectorAll('img,[data-src]');
                        let c = 0;
                        for (let i of imgs) {
                            let s = i.src || i.getAttribute('data-src') || '';
                            if ((s.includes('googleusercontent') || s.includes('ggpht')) && !s.includes('w32-h32') && !s.includes('w48-h48')) c++;
                        }
                        return c;
                    }
                """)
                if cur == prev_count:
                    stale += 1
                    if stale >= 6:
                        break
                else:
                    stale = 0
                    prev_count = cur

        # -- Extract image URLs --
        all_imgs = await page.evaluate("""
            () => {
                let out = new Set();
                document.querySelectorAll('img,[data-src]').forEach(el => {
                    let s = el.getAttribute('data-src') || el.src || '';
                    if (s && (s.includes('googleusercontent') || s.includes('ggpht'))) out.add(s);
                });
                document.querySelectorAll('[style*="googleusercontent"],[style*="ggpht"]').forEach(el => {
                    let style = el.getAttribute('style') || '';
                    for (let m of style.matchAll(/url\(\"?([^\"')]+(?:googleusercontent|ggpht)[^\"')]+)\"?\)/g)) {
                        out.add(m[1]);
                    }
                });
                document.querySelectorAll('img[srcset]').forEach(img => {
                    for (let part of (img.getAttribute('srcset') || '').split(',')) {
                        let u = part.trim().split(' ')[0];
                        if (u && (u.includes('googleusercontent') || u.includes('ggpht'))) out.add(u);
                    }
                });
                return Array.from(out);
            }
        """)

        seen = set()
        image_urls = []
        for src in all_imgs:
            if len(image_urls) >= max_images:
                break
            if not is_valid_img(src):
                continue
            base = canonical_img_url(src)
            if base not in seen:
                seen.add(base)
                image_urls.append(base + "=w1200-h900")

        await browser.close()

    return {
        "place_name": place_name,
        "address": address,
        "phone": phone,
        "rating": rating,
        "image_urls": image_urls,
        "status": "success" if image_urls else "no_images",
    }


@router.post("/simple-scrape")
def simple_scrape(request: SimpleScrapeRequest):
    """Scrape a Google Maps place URL and return images immediately."""
    try:
        result = asyncio.run(_do_scrape(request.url, request.max_images))
        return result
    except Exception as e:
        return {
            "place_name": "Error",
            "address": "",
            "phone": "",
            "rating": "",
            "image_urls": [],
            "status": f"error: {str(e)}",
        }
