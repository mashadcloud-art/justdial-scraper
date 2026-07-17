"""
Map Scraper module: drives the "Map Scraper" Node/Puppeteer service running on the
thozil server (mmap-scrap/cloud-scrap/server.js) over its HTTP API — manages saved
scrapers, triggers quick/saved Google Maps scrapes, pulls back results, and syncs
them into our own Supabase `listings` table tagged category="Google Maps".
"""
import os
import re
import time
import threading
from datetime import datetime
from typing import Optional

import requests

from app.database import SessionLocal
from app import models
from app.scraper.category_normalizer import normalize_category
from app.scraper.emulator_parser import get_state_from_district

THOZIL_BASE_URL = os.environ.get("MAP_SCRAPER_URL", "http://152.67.165.254:3001").rstrip("/")
CONNECT_TIMEOUT = 8
REQUEST_TIMEOUT = 15
SCRAPE_TIMEOUT = 300  # the remote /api/scrape and /api/scrapers/:id/run calls can run a real headless browse
RUN_WATCH_TIMEOUT = 300  # how long to wait for a saved scraper's result file to appear, for auto-sync

_state_lock = threading.Lock()
_state = {
    "running": False,
    "last_query": None,
    "last_result_count": 0,
    "last_synced": 0,
    "total_synced": 0,
    "last_sync_at": None,
    "last_error": None,
    "last_run_at": None,
}


def _record_sync(synced: int):
    with _state_lock:
        _state["last_synced"] = synced
        _state["total_synced"] += synced
        _state["last_sync_at"] = datetime.utcnow().isoformat()

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


# ─── Quick scrape (POST /api/scrape) ─────────────────────────────────────────

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
            _log(f"Starting quick scrape on thozil: {query}")
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
                _record_sync(synced)
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
            _log("Quick scrape task completed.")

    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "query": query}


# ─── Saved scrapers (GET/POST /api/scrapers, POST /api/scrapers/:id/run) ────

def list_scrapers() -> dict:
    try:
        resp = requests.get(_url("/api/scrapers"), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        items = list(data.values()) if isinstance(data, dict) else (data or [])
        items.sort(key=lambda s: s.get("created") or "", reverse=True)
        return {"ok": True, "scrapers": items}
    except requests.RequestException as e:
        return {"ok": False, "error": str(e), "scrapers": []}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "scraper").lower()).strip("-")
    return f"{slug or 'scraper'}-{int(time.time())}"


def create_scraper(scraper_id: Optional[str], name: str, type_: str, config: dict,
                    schedule: Optional[str] = None) -> dict:
    payload = {
        "id": scraper_id or _slugify(name),
        "name": name or scraper_id,
        "type": type_,
        "config": config,
        "schedule": schedule or None,
    }
    try:
        resp = requests.post(_url("/api/scrapers"), json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        _log(f"Created saved scraper '{payload['id']}' ({type_}).")
        return {"ok": True, **data}
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


def delete_scraper(scraper_id: str) -> dict:
    try:
        resp = requests.delete(_url(f"/api/scrapers/{scraper_id}"), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        _log(f"Deleted saved scraper '{scraper_id}'.")
        return {"ok": True}
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


def run_scraper(scraper_id: str, auto_sync: bool = True, district: str = "", category: str = "") -> dict:
    try:
        before = set(_list_result_filenames())
    except requests.RequestException:
        before = set()

    try:
        resp = requests.post(_url(f"/api/scrapers/{scraper_id}/run"), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        _log(f"Failed to run saved scraper '{scraper_id}': {e}", ok=False)
        return {"ok": False, "error": str(e)}

    _log(f"Triggered saved scraper '{scraper_id}' on thozil.")

    if auto_sync:
        threading.Thread(
            target=_watch_and_sync_run, args=(scraper_id, before, district, category), daemon=True
        ).start()

    return {"ok": True}


def _watch_and_sync_run(scraper_id: str, before: set, district: str, category: str):
    """Poll /api/results until the saved scraper's output file shows up, then sync it."""
    prefix = f"{scraper_id}-"
    deadline = time.time() + RUN_WATCH_TIMEOUT
    while time.time() < deadline:
        time.sleep(5)
        try:
            current = _list_result_filenames()
        except requests.RequestException:
            continue
        new_files = [f for f in current if f not in before and f.startswith(prefix)]
        if new_files:
            filename = new_files[0]
            _log(f"Detected new result '{filename}' for scraper '{scraper_id}'.")
            try:
                data = get_result(filename)
                businesses = data.get("businesses") or data.get("items") or []
                synced = sync_businesses(businesses, district=district, category=category)
                _record_sync(synced)
                with _state_lock:
                    _state["last_result_count"] = len(businesses)
                _log(f"Synced {synced} listings from '{filename}' to Supabase.")
            except Exception as e:
                _log(f"Auto-sync for '{filename}' failed: {e}", ok=False)
            return
    _log(f"Timed out waiting for scraper '{scraper_id}' result to appear.", ok=False)


# ─── Results (GET /api/results, /api/results/:filename[/download|/csv]) ────

def _list_result_filenames() -> list:
    resp = requests.get(_url("/api/results"), timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def list_results() -> dict:
    try:
        return {"ok": True, "files": _list_result_filenames()}
    except requests.RequestException as e:
        return {"ok": False, "error": str(e), "files": []}


def get_result(filename: str) -> dict:
    resp = requests.get(_url(f"/api/results/{filename}"), timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def download_result(filename: str):
    resp = requests.get(_url(f"/api/results/{filename}/download"), timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/json")


def get_result_csv(filename: str) -> str:
    resp = requests.get(_url(f"/api/results/{filename}/csv"), timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


# ─── Sync to Supabase `listings` ─────────────────────────────────────────────

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


def sync_result(filename: Optional[str], district: str = "", category: str = "") -> dict:
    """Sync a specific result file, or the most recent one if no filename is given."""
    if not filename:
        listing = list_results()
        if not listing["ok"] or not listing["files"]:
            return {"ok": False, "error": listing.get("error", "No results available"), "synced": 0, "found": 0}
        filename = listing["files"][0]

    try:
        data = get_result(filename)
    except requests.RequestException as e:
        return {"ok": False, "error": str(e), "synced": 0, "found": 0}

    businesses = data.get("businesses") or data.get("items") or []
    synced = sync_businesses(businesses, district=district, category=category)
    _record_sync(synced)
    return {"ok": True, "synced": synced, "found": len(businesses), "filename": filename}
