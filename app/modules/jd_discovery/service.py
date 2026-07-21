"""
Stage 1 discovery: scroll the real JustDial search-results page (not the internal
JSON API) and save each result card's URL/name/area/rating/category/image URLs.
Never visits individual listing pages — that's Stage 2 (deep_scrape's
enrich_pending_listings), which consumes whatever this leaves `enrichment_status
== "pending"`.
"""
import re
import time
from datetime import datetime

from app.database import SessionLocal
from app import models

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CARD_LINK_MARKER = "_BZDET"  # proven anchor pattern for JD result-card links (see app/scraper/playwright_scraper.py)
MAX_SCROLL_ROUNDS = 80
SCROLL_PAUSE_SECONDS = 1.5
STALL_ROUNDS_TO_STOP = 4  # consecutive no-new-card scrolls before we conclude the list is exhausted


def _parse_listing_id(href: str) -> str | None:
    m = re.search(r'(\d+)_BZDET', href)
    return m.group(1) if m else None


def _extract_cards(html: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    seen_in_page = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if CARD_LINK_MARKER not in href:
            continue
        listing_id = _parse_listing_id(href)
        if not listing_id or listing_id in seen_in_page:
            continue
        name = a.get_text(strip=True)
        if not name or name.startswith("+") or "more" in name.lower():
            continue
        seen_in_page.add(listing_id)

        # Climb to the nearest ancestor that has BOTH an image and a rating-shaped
        # number — requiring both (not either) avoids stopping at a half-formed
        # wrapper that's actually shared with a sibling card. If nothing matches
        # within a few levels, fall back to the immediate parent only, so we never
        # risk grabbing a shared ancestor and bleeding fields across cards.
        container = None
        climb = a
        for _ in range(6):
            parent = climb.find_parent()
            if parent is None:
                break
            climb = parent
            text = climb.get_text(" ", strip=True)
            if climb.find("img") is not None and re.search(r'[0-5]\.\d', text):
                container = climb
                break
        if container is None:
            container = a.find_parent() or a

        card_text = container.get_text(" ", strip=True)

        rating, rating_count = None, None
        m = re.search(r'([0-5]\.\d)\D{0,20}?(\d+)\s*[Rr]atings?', card_text)
        if m:
            rating, rating_count = m.group(1), int(m.group(2))
        else:
            m2 = re.search(r'\b([0-5]\.\d)\b', card_text)
            if m2:
                rating = m2.group(1)

        images = []
        for img in container.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if src.startswith("http") and src not in images:
                images.append(src)
        images = images[:6]

        href_full = href if href.startswith("http") else f"https://www.justdial.com{href}"

        cards.append({
            "jd_listing_id": listing_id,
            "jd_url": href_full,
            "name": name,
            "rating": rating,
            "rating_count": rating_count,
            "images": images,
        })
    return cards


def _upsert_listing(db, card: dict, district: str, category: str) -> bool:
    exists = db.query(models.Listing.id).filter(models.Listing.jd_listing_id == card["jd_listing_id"]).first()
    if exists:
        return False

    listing = models.Listing(
        name=card["name"],
        jd_url=card["jd_url"],
        jd_listing_id=card["jd_listing_id"],
        category=category,
        district=district,
        rating=card["rating"],
        rating_count=card["rating_count"],
        enrichment_status="pending",
        scraped_at=datetime.utcnow(),
    )
    db.add(listing)
    db.flush()  # assign listing.id before attaching images

    for idx, url in enumerate(card["images"]):
        db.add(models.ListingImage(listing_id=listing.id, image_path=url, category="discovery", is_primary=(idx == 0)))

    return True


def discover(district: str, category: str, max_scroll_rounds: int = MAX_SCROLL_ROUNDS, status: dict | None = None) -> dict:
    """Scroll the JustDial search-results page for `category` in `district` until no new
    cards load, saving each new one. Returns {"found": N, "saved": M}."""
    from playwright.sync_api import sync_playwright

    if status is None:
        status = {}
    slug_district = district.replace(" ", "-")
    slug_category = category.replace(" ", "-")
    url = f"https://www.justdial.com/{slug_district}/{slug_category}"
    status["url"] = url

    found_cards: dict[str, dict] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent=USER_AGENT, viewport={"width": 1366, "height": 900}).new_page()
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(3)

        stall_rounds = 0
        for round_num in range(max_scroll_rounds):
            for card in _extract_cards(page.content()):
                if card["jd_listing_id"] not in found_cards:
                    found_cards[card["jd_listing_id"]] = card

            status["found"] = len(found_cards)
            status["round"] = round_num + 1

            new_this_round = len(found_cards) - status.get("_prev_found", 0)
            status["_prev_found"] = len(found_cards)

            if new_this_round <= 0:
                stall_rounds += 1
                if stall_rounds >= STALL_ROUNDS_TO_STOP:
                    break
            else:
                stall_rounds = 0

            page.mouse.wheel(0, 4000)
            time.sleep(SCROLL_PAUSE_SECONDS)
            # Some categories paginate via a "Load more"/"Next" control instead of pure
            # infinite scroll — click it if present so we don't stall out early.
            try:
                page.evaluate('''() => {
                    const els = document.querySelectorAll('a, button, div, span');
                    for (const el of els) {
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t === 'load more' || t === 'show more' || t === 'next') { el.click(); return; }
                    }
                }''')
            except Exception:
                pass

        browser.close()

    db = SessionLocal()
    saved = 0
    try:
        for card in found_cards.values():
            if _upsert_listing(db, card, district, category):
                saved += 1
        db.commit()
    finally:
        db.close()

    status["done"] = True
    status["saved"] = saved
    status["found"] = len(found_cards)
    return {"found": len(found_cards), "saved": saved}
