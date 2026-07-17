"""
Map Scraper module: drives the "Map Scraper" Node/Puppeteer service running on the
thozil server (mmap-scrap/cloud-scrap/server.js) over its HTTP API — starts Google
Maps scrapes, pulls back results, and syncs them into our own Supabase `listings`
table tagged category="Google Maps".
"""
import os
import threading
from datetime import datetime
from typing import Optional

import requests

from app.database import SessionLocal
from app import models
from app.scraper.category_normalizer import normalize_category
from app.scraper.emulator_parser import get_state_from_district

THOZIL_BASE_URL = os.environ.get("MAP_SCRAPER_URL", "http://152.67.165.254:3000").rstrip("/")
CONNECT_TIMEOUT = 8
REQUEST_TIMEOUT = 15
SCRAPE_TIMEOUT = 300  # the remote /api/scrape call blocks until Puppeteer finishes

_state_lock = threading.Lock()
_state = {
    "running": False,
    "last_query": None,
    "last_result_count": 0,
    "last_synced": 0,
    "last_error": None,
    "last_run_at": None,
}

_log_lock = threading.Lock()
_logs: list = []


def _log(msg: str, ok: bool = True):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": msg, "ok": ok}
    with _log_lock:
        _logs.append(entry)
        if len(_logs) > 500:
            del _logs[:-500]
    print(f"[map_scraper] {msg}")


def get_log(last_idx: int = 0) -> dict:
    with _log_lock:
        new_logs = _logs[last_idx:]
        next_idx = len(_logs)
    return {"logs": new_logs, "next_idx": next_idx}


def _url(path: str) -> str:
    return f"{THOZIL_BASE_URL}{path}"


def is_connected() -> bool:
    try:
        resp = requests.get(_url("/api/scrapers"), timeout=CONNECT_TIMEOUT)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def get_status() -> dict:
    with _state_lock:
        state_copy = dict(_state)
    return {"connected": is_connected(), "base_url": THOZIL_BASE_URL, **state_copy}


def _build_query(district: str, category: str) -> str:
    category = (category or "").strip()
    district = (district or "").strip()
    if category and district:
        return f"{category} in {district}"
    return category or district


def start_scrape(district: str, category: str, max_results: int = 100, auto_sync: bool = True) -> dict:
    with _state_lock:
        if _state["running"]:
            return {"ok": False, "error": "A Map Scraper run is already in progress"}
        if not category and not district:
            return {"ok": False, "error": "category or district is required"}
        query = _build_query(district, category)
        _state["running"] = True
        _state["last_query"] = query
        _state["last_error"] = None

    def run():
        try:
            _log(f"Starting Map Scraper run on thozil: {query}")
            resp = requests.post(
                _url("/api/scrape"),
                json={"type": "google-maps", "query": query, "maxResults": max_results},
                timeout=SCRAPE_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success") is False:
                raise RuntimeError(data.get("error", "Remote scrape reported failure"))

            businesses = data.get("businesses", [])
            with _state_lock:
                _state["last_result_count"] = len(businesses)
                _state["last_run_at"] = datetime.utcnow().isoformat()
            _log(f"Map Scraper found {len(businesses)} results (saved as {data.get('savedTo')}).")

            if auto_sync and businesses:
                synced = sync_businesses(businesses, district=district, category=category)
                with _state_lock:
                    _state["last_synced"] = synced
                _log(f"Synced {synced} listings to Supabase (category=Google Maps).")
        except requests.RequestException as e:
            with _state_lock:
                _state["last_error"] = str(e)
            _log(f"Map Scraper request to thozil failed: {e}", ok=False)
        except Exception as e:
            with _state_lock:
                _state["last_error"] = str(e)
            _log(f"Map Scraper run failed: {e}", ok=False)
        finally:
            with _state_lock:
                _state["running"] = False
            _log("Map Scraper task completed.")

    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "query": query}


def get_results(limit: int = 1) -> dict:
    """Fetch the filename list from thozil, then pull the content of the most recent `limit` files."""
    try:
        resp = requests.get(_url("/api/results"), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        filenames = resp.json()
    except requests.RequestException as e:
        return {"ok": False, "error": str(e), "files": [], "businesses": []}

    businesses = []
    for filename in filenames[:max(1, limit)]:
        try:
            r = requests.get(_url(f"/api/results/{filename}"), timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            items = data.get("businesses") or data.get("items") or []
            for item in items:
                item["_source_file"] = filename
            businesses.extend(items)
        except requests.RequestException:
            continue

    return {"ok": True, "files": filenames, "businesses": businesses}


def sync_businesses(businesses: list, district: str = "", category: str = "") -> int:
    """Dedup-insert scraped Google Maps businesses into the `listings` table, tagged category='Google Maps'."""
    state = get_state_from_district(district) if district else ""
    synced = 0
    db = SessionLocal()
    try:
        for biz in businesses:
            name = (biz.get("name") or "").strip()
            if not name:
                continue
            source_url = biz.get("link") or biz.get("website") or ""
            address = biz.get("address") or ""
            phone = biz.get("phone") or ""
            hours = biz.get("hours") or ""
            scraped_category = (biz.get("category") or category or "").strip()
            normalized = normalize_category(scraped_category) if scraped_category else "Other"

            existing = None
            if source_url:
                existing = db.query(models.Listing).filter(models.Listing.jd_url == source_url).first()
            if existing is None and phone:
                existing = db.query(models.Listing).filter(
                    models.Listing.phone == phone, models.Listing.name == name
                ).first()
            if existing is None:
                existing = db.query(models.Listing).filter(
                    models.Listing.name == name, models.Listing.address == address
                ).first()

            if existing:
                existing.category = "Google Maps"
                if scraped_category:
                    existing.subcategory = scraped_category
                existing.normalized_category = normalized
                if address:
                    existing.address = address
                if phone:
                    existing.phone = phone
                if hours:
                    existing.opening_hours = hours
                if district:
                    existing.district = district
                if state:
                    existing.state = state
                existing.scraped_at = datetime.utcnow()
            else:
                db.add(models.Listing(
                    name=name,
                    address=address,
                    phone=phone,
                    jd_url=source_url,
                    category="Google Maps",
                    subcategory=scraped_category or None,
                    normalized_category=normalized,
                    opening_hours=hours,
                    district=district or "",
                    state=state or "",
                ))
            synced += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return synced


def sync_latest(district: str = "", category: str = "", limit: int = 1) -> dict:
    result = get_results(limit=limit)
    if not result["ok"]:
        return {"ok": False, "error": result.get("error"), "synced": 0, "found": 0}
    synced = sync_businesses(result["businesses"], district=district, category=category)
    with _state_lock:
        _state["last_synced"] = synced
    return {"ok": True, "synced": synced, "found": len(result["businesses"])}
