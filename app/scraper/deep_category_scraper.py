"""
Deep Category Scraper
======================
Given a JustDial category page URL (e.g. https://www.justdial.com/Kasaragod/Hospitals/nct-10253670),
resolves the subcategories for that category (e.g. Children Hospitals, ENT Hospitals, Eye Hospitals)
from the `jd_category_map` table — seeded with defaults for Hospitals/Doctors/Restaurants, and
extendable by pasting a category page's HTML (JustDial blocks automated fetches of that page, so this
module never fetches one itself) — then loops through every subcategory and scrapes all listings using
the existing JWT scraper in jd_api_scraper.py.

Supports:
  - district mode: only the city found in the URL
  - state mode: all 14 Kerala districts

Progress (including a rolling live-log tail) is written to the `scrape_jobs` table so the frontend can
poll job status.
"""
import json as _json
import re
import time
from datetime import datetime

from app.database import SessionLocal
from app import models

# Default subcategories seeded into jd_category_map (city=None → applies to every city) the first
# time each main_category is looked up. Extend coverage for other categories by pasting HTML instead.
SEED_CATEGORY_MAP: dict[str, list[str]] = {
    "HOSPITALS": ["Children Hospitals", "ENT Hospitals", "Eye Hospitals", "Maternity Hospitals",
                  "Mental Hospitals", "Multispeciality Hospitals", "Private Hospitals", "Public Hospitals",
                  "Veterinary Hospitals", "Ayurvedic Hospitals", "Cancer Hospitals", "Cardiac Hospitals",
                  "Charitable Hospitals", "Dental Hospitals", "Diabetic Centres", "Homeopathic Hospitals",
                  "Kidney Hospitals", "Neurological Hospitals", "Nursing Homes", "Orthopaedic Hospitals"],
    "DOCTORS": ["General Physicians", "Dentists", "Gynaecologists", "Paediatricians", "Dermatologists",
                "Ophthalmologists", "ENT Specialists", "Orthopaedic Doctors", "Cardiologists", "Neurologists",
                "Psychiatrists", "Urologists", "Oncologists", "Endocrinologists"],
    "RESTAURANTS": ["Fast Food", "Chinese", "North Indian", "South Indian", "Bakeries", "Cafes",
                    "Ice Cream Parlours", "Juice Shops"],
}

MAX_LOG_LINES = 300


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


def ensure_seed_category_map(db):
    """Seed jd_category_map with SEED_CATEGORY_MAP defaults, once per main_category (city=None rows)."""
    for main_category, subs in SEED_CATEGORY_MAP.items():
        exists = db.query(models.JDCategoryMap).filter(
            models.JDCategoryMap.main_category.ilike(main_category)
        ).first()
        if exists:
            continue
        for sub in subs:
            db.add(models.JDCategoryMap(main_category=main_category.title(), subcategory=sub, tags=None, city=None))
    db.commit()


def get_subcategories_from_map(db, main_category: str, city: str | None = None) -> list[dict]:
    """Look up subcategories for a main category — global (city=None) entries plus any saved for this city."""
    rows = db.query(models.JDCategoryMap).filter(
        models.JDCategoryMap.main_category.ilike(main_category)
    ).all()
    seen = set()
    results = []
    for r in rows:
        if r.city and (not city or r.city.strip().lower() != city.strip().lower()):
            continue
        name_lower = r.subcategory.strip().lower()
        if name_lower in seen:
            continue
        seen.add(name_lower)
        results.append({"name": r.subcategory, "tags": r.tags})
    return results


def save_html_subcategories_to_map(db, main_category: str, html_content: str, city: str | None = None) -> list[dict]:
    """Parse a pasted JustDial category page and upsert its subcategories (+ tags) into jd_category_map."""
    from app.api.categories import _parse_categories_from_html

    raw_subs = _parse_categories_from_html(html_content)
    cat_lower = main_category.strip().lower()
    saved = []
    seen_names = set()
    for s in raw_subs:
        name = s["name"].strip()
        if not name or name.lower() == cat_lower or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        tag = s.get("key")

        query = db.query(models.JDCategoryMap).filter(
            models.JDCategoryMap.main_category.ilike(main_category),
            models.JDCategoryMap.subcategory.ilike(name),
        )
        query = query.filter(models.JDCategoryMap.city == city) if city else query.filter(models.JDCategoryMap.city.is_(None))
        if not query.first():
            db.add(models.JDCategoryMap(main_category=main_category, subcategory=name, tags=tag, city=city))
        saved.append({"name": name, "tags": tag})
    db.commit()
    return saved


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


def _checkpoint(db, job_id: str) -> bool:
    """
    Called between subcategories. Blocks while the job is paused (re-checking every second),
    and returns True once the job should stop entirely (control == "stop").
    """
    while True:
        job = db.query(models.DeepScrapeJob).filter(models.DeepScrapeJob.job_id == job_id).first()
        if not job:
            return True
        if job.control == "stop":
            return True
        if job.control != "pause":
            return False
        time.sleep(1)


def _log(db, job_id: str, message: str):
    """Append a line to the job's rolling log tail (used by the frontend's live log panel)."""
    job = db.query(models.DeepScrapeJob).filter(models.DeepScrapeJob.job_id == job_id).first()
    if not job:
        return
    lines = _json.loads(job.log_tail) if job.log_tail else []
    lines.append(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {message}")
    if len(lines) > MAX_LOG_LINES:
        lines = lines[-MAX_LOG_LINES:]
    job.log_tail = _json.dumps(lines)
    db.commit()
    print(f"[deep_category_scraper] {message}")


def scrape_places_for_subcategory(job_id: str, db, district: str, subcategory_name: str, place_names: list[str],
                                   seen_ids: set, seen_phones: set, stats: dict,
                                   pages_per_place: int = 2, limit: int = 100):
    """
    Scrapes a subcategory across many named localities within a district (e.g. pincode-derived
    post office place names), reusing the raw JWT request/parse/save building blocks from
    jd_api_scraper.py unmodified — mirrors the same "<category> in <place>" query convention
    jd_api_scraper.py already uses for its own curated "area" targets, just with a much larger
    place list.

    `seen_ids`/`seen_phones`/`stats` are shared across the whole job (every subcategory and every
    pincode/place) so the same business showing up under multiple pincode searches is only saved once.
    """
    from jd_api_scraper import scrape_jd_api, parse_row, save_to_db

    total_inserted = 0
    total_updated = 0
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

                doc_id = listing.get("doc_id")
                phone = listing.get("phone")
                is_dupe = (doc_id and doc_id in seen_ids) or (phone and phone in seen_phones)

                if is_dupe:
                    stats["skipped"] += 1
                else:
                    if doc_id:
                        seen_ids.add(doc_id)
                    if phone:
                        seen_phones.add(phone)
                    inserted, updated = save_to_db(db, listing, subcategory_name)
                    if inserted:
                        stats["saved"] += 1
                        total_inserted += 1
                    elif updated:
                        stats["updated"] += 1
                        total_updated += 1
                    else:
                        stats["skipped"] += 1

                stats["processed"] += 1
                if stats["processed"] % 50 == 0:
                    _log(db, job_id, f"Skipped {stats['skipped']} duplicates, Saved {stats['saved']} unique, Updated {stats['updated']} existing")

            next_cursor = result.get("next_cursor")
            if not next_cursor:
                break
    return total_inserted, total_updated


def run_deep_scrape_job(job_id: str, url: str, mode: str, manual_subcategories: list = None):
    """
    Main orchestration entry point. Intended to run in a background thread.
    Phase 1: resolve subcategories once from jd_category_map, save to jd_categories for every target
      city — subcategory names are the same taxonomy across cities, so there's no need to look them
      up per city.
    Phase 2: scrape every (city, subcategory) pair.
      - district mode: scrapes each subcategory across every verified pincode-derived locality in the
        district (via scrape_places_for_subcategory), deduplicating against one seen_ids/seen_phones
        set shared across the entire job — far denser coverage than the curated ~12-place "famous
        places" list, without re-saving the same business twice.
      - state mode: unchanged, uses the existing jd_api_scraper.scrape_jwt_city() per district (no
        cross-call dedup hook is available there, so only district mode gets the shared dedup set).
    """
    from jd_api_scraper import scrape_jwt_city
    from app.scraper.constants import CITIES

    db = SessionLocal()
    try:
        origin_city, category_name = parse_category_url(url)
        _log(db, job_id, f"Job started: {mode} mode for '{category_name}' ({origin_city})")

        if mode == "state":
            target_cities = [d for d in CITIES.get("Kerala", []) if d != "All"]
        else:
            target_cities = [origin_city]

        _update_job(db, job_id, status="discovering")

        ensure_seed_category_map(db)
        subs = get_subcategories_from_map(db, category_name, city=origin_city)

        # Use manual subcategories if provided and nothing found in map
        if not subs and manual_subcategories:
            _log(db, job_id, f"Using {len(manual_subcategories)} manually provided subcategories.")
            subs = [{"name": s, "tags": None} for s in manual_subcategories]

        if not subs:
            _log(db, job_id, "No subcategories found in jd_category_map for this category.")
            _update_job(db, job_id, status="failed", current_subcategory=(
                "No subcategories found — paste the category page's HTML to add some, or use a "
                "category with a built-in list (Hospitals, Doctors, Restaurants)."
            ))
            return
        _log(db, job_id, f"Resolved {len(subs)} subcategories: {', '.join(s['name'] for s in subs)}")

        work_items = []  # list of (city, subcategory_name)
        for city in target_cities:
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
            _log(db, job_id, "Verifying pincode localities against JustDial...")
            district_places = get_verified_place_names_for_district(origin_city, category_hint=category_name)
            _log(db, job_id, f"Verified {len(district_places)} localities in {origin_city}.")

        # Shared across every subcategory and every pincode/place in this job.
        seen_ids: set = set()
        seen_phones: set = set()
        stats = {"processed": 0, "saved": 0, "updated": 0, "skipped": 0}

        stopped = False
        for city, subcat_name in work_items:
            if _checkpoint(db, job_id):
                stopped = True
                break

            label = subcat_name if mode == "district" else f"{subcat_name} ({city})"
            _update_job(db, job_id, current_subcategory=label)
            _log(db, job_id, f"Scraping '{label}'...")

            try:
                if mode == "district" and district_places:
                    inserted, updated = scrape_places_for_subcategory(
                        job_id, db, city, subcat_name, district_places, seen_ids, seen_phones, stats
                    )
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
                _log(db, job_id, f"Failed scraping '{subcat_name}' in '{city}': {e}")

            job = db.query(models.DeepScrapeJob).filter(models.DeepScrapeJob.job_id == job_id).first()
            if job:
                job.completed_subcategories += 1
                job.total_found += (inserted + updated)
                job.duplicates_skipped += updated
                db.commit()

        if stopped:
            _log(db, job_id, "Job stopped by user.")
            _update_job(db, job_id, status="stopped", current_subcategory=None)
        else:
            _log(db, job_id, (
                f"Job complete. Skipped {stats['skipped']} duplicates, Saved {stats['saved']} unique, "
                f"Updated {stats['updated']} existing." if mode == "district" and district_places else "Job complete."
            ))
            _update_job(db, job_id, status="completed", current_subcategory=None)
    except Exception as e:
        _log(db, job_id, f"Job failed: {e}")
        try:
            _update_job(db, job_id, status="failed")
        except Exception:
            pass
    finally:
        db.close()
