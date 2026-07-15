"""
Deep Category Scraper
======================
Given a JustDial category page URL (e.g. https://www.justdial.com/Kasaragod/Hospitals/nct-10253670),
discovers every subcategory listed on that page (e.g. Children Hospitals, ENT Hospitals, Eye Hospitals),
saves them to the `jd_categories` table, then loops through every discovered subcategory and scrapes
all listings using the existing JWT scraper in jd_api_scraper.py.

Supports:
  - district mode: only the city found in the URL
  - state mode: all 14 Kerala districts

Progress is written to the `scrape_jobs` table so the frontend can poll job status.
"""
import re

from app.database import SessionLocal
from app import models
from app.scraper.category_fetcher import format_city_for_url, format_category_for_url


def parse_category_url(url: str):
    """Extract (city, category) from a JustDial category page URL."""
    match = re.search(r'justdial\.com/([^/]+)/([^/]+)', url)
    if not match:
        raise ValueError(f"Could not parse city/category from URL: {url}")
    city = match.group(1).replace('-', ' ').strip()
    category = match.group(2).replace('-', ' ').strip()
    return city, category


def extract_nct_code(url: str):
    match = re.search(r'nct-(\d+)', url or "")
    return match.group(1) if match else None


def build_city_category_url(city: str, category: str) -> str:
    return f"https://www.justdial.com/{format_city_for_url(city)}/{format_category_for_url(category)}"


def discover_subcategories(url: str, category_name: str) -> list[dict]:
    """Scrape a JustDial category page and return its listed subcategories."""
    from app.api.categories import _fetch_html_page, _parse_categories_from_html

    html = _fetch_html_page(url)
    if not html:
        return []

    raw_subs = _parse_categories_from_html(html)
    cat_lower = category_name.lower()
    seen_names = set()
    results = []
    for s in raw_subs:
        name = s["name"].strip()
        if not name or name.lower() == cat_lower or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        results.append({"name": name, "nct_code": extract_nct_code(s.get("url", ""))})
    return results


def save_subcategories_to_db(db, city: str, parent_category: str, subcats: list[dict]) -> list[str]:
    """Persist newly-discovered subcategories to jd_categories (skips ones already saved)."""
    names = []
    for sc in subcats:
        existing = db.query(models.JDCategory).filter(
            models.JDCategory.city == city,
            models.JDCategory.parent_category == parent_category,
            models.JDCategory.subcategory_name == sc["name"]
        ).first()
        if not existing:
            db.add(models.JDCategory(
                city=city,
                parent_category=parent_category,
                subcategory_name=sc["name"],
                subcategory_nct_code=sc.get("nct_code"),
            ))
        names.append(sc["name"])
    db.commit()
    return names


def _update_job(db, job_id: str, **fields):
    job = db.query(models.DeepScrapeJob).filter(models.DeepScrapeJob.job_id == job_id).first()
    if not job:
        return None
    for key, value in fields.items():
        setattr(job, key, value)
    db.commit()
    return job


def scrape_places_for_subcategory(district: str, subcategory_name: str, place_names: list[str], pages_per_place: int = 2, limit: int = 100):
    """
    Scrapes a subcategory across many named localities within a district (e.g. pincode-derived
    post office place names), reusing the raw JWT request/parse/save building blocks from
    jd_api_scraper.py unmodified — mirrors the same "<category> in <place>" query convention
    jd_api_scraper.py already uses for its own curated "area" targets, just with a much larger
    place list.
    """
    from jd_api_scraper import scrape_jd_api, parse_row, save_to_db

    db = SessionLocal()
    total_inserted = 0
    total_updated = 0
    try:
        for place in place_names:
            next_cursor = None
            for _page in range(pages_per_place):
                result = scrape_jd_api(district, f"{subcategory_name} in {place}", limit=limit, nextdocid=next_cursor)
                rows = result.get("rows", [])
                columns = result.get("columns", [])
                if not rows:
                    break
                for row in rows:
                    listing = parse_row(columns, row, district, subcategory_name)
                    if not listing or not listing["name"]:
                        continue
                    inserted, updated = save_to_db(db, listing, subcategory_name)
                    if inserted:
                        total_inserted += 1
                    elif updated:
                        total_updated += 1
                next_cursor = result.get("next_cursor")
                if not next_cursor:
                    break
    finally:
        db.close()
    return total_inserted, total_updated


def run_deep_scrape_job(job_id: str, url: str, mode: str):
    """
    Main orchestration entry point. Intended to run in a background thread.
    Phase 1: discover subcategories for every target city, save to jd_categories.
    Phase 2: scrape every (city, subcategory) pair.
      - district mode: scrapes each subcategory across every verified pincode-derived
        locality in the district (via scrape_places_for_subcategory) — far denser
        coverage than the curated ~12-place "famous places" list.
      - state mode: unchanged, uses the existing jd_api_scraper.scrape_jwt_city() per district.
    """
    from jd_api_scraper import scrape_jwt_city
    from app.scraper.constants import CITIES

    db = SessionLocal()
    try:
        origin_city, category_name = parse_category_url(url)

        if mode == "state":
            target_cities = [d for d in CITIES.get("Kerala", []) if d != "All"]
        else:
            target_cities = [origin_city]

        _update_job(db, job_id, status="discovering")

        work_items = []  # list of (city, subcategory_name)
        for city in target_cities:
            city_url = url if city.lower() == origin_city.lower() else build_city_category_url(city, category_name)
            subs = discover_subcategories(city_url, category_name)
            saved_names = save_subcategories_to_db(db, city, category_name, subs)
            for name in saved_names:
                work_items.append((city, name))

        if not work_items:
            _update_job(db, job_id, status="failed", current_subcategory="No subcategories found on this page")
            return

        _update_job(db, job_id, status="scraping", total_subcategories=len(work_items))

        district_places = None
        if mode == "district":
            from app.api.pincodes import get_verified_place_names_for_district
            _update_job(db, job_id, current_subcategory="Verifying pincode localities against JustDial...")
            district_places = get_verified_place_names_for_district(origin_city, category_hint=category_name)

        for city, subcat_name in work_items:
            label = subcat_name if mode == "district" else f"{subcat_name} ({city})"
            _update_job(db, job_id, current_subcategory=label)

            try:
                if mode == "district" and district_places:
                    inserted, updated = scrape_places_for_subcategory(city, subcat_name, district_places)
                else:
                    inserted, updated = scrape_jwt_city(
                        district=city,
                        category=subcat_name,
                        pages=5,
                        limit=100,
                        dry_run=False,
                        subcategories=False,
                        use_proxy=False,
                    )
            except Exception as e:
                inserted, updated = 0, 0
                print(f"[deep_category_scraper] Failed scraping '{subcat_name}' in '{city}': {e}")

            job = db.query(models.DeepScrapeJob).filter(models.DeepScrapeJob.job_id == job_id).first()
            if job:
                job.completed_subcategories += 1
                job.total_found += (inserted + updated)
                job.duplicates_skipped += updated
                db.commit()

        _update_job(db, job_id, status="completed", current_subcategory=None)
    except Exception as e:
        print(f"[deep_category_scraper] Job {job_id} failed: {e}")
        try:
            _update_job(db, job_id, status="failed")
        except Exception:
            pass
    finally:
        db.close()
