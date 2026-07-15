"""
Scraper module: trigger web/ADB/API/Playwright/Google Maps scrapes, ingest
listings, and control ADB devices/proxy/screen-mirroring.

Also re-exposes the existing app/api/categories.py and app/api/pincodes.py
routers unchanged — those two files stay at their current import path
because jd_api_scraper.py and app/scraper/deep_category_scraper.py import
directly from them and must not be touched.
"""
import sys
import os
import shutil
import datetime
import json
import time
import glob
import threading
import subprocess
from typing import Optional, List

from fastapi import (
    APIRouter, Depends, UploadFile, File, Form, HTTPException,
    BackgroundTasks, Request, Header
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from config import settings
from app.scraper.emulator_parser import (
    get_state_from_district,
    extract_place_from_address,
    detect_category_from_name,
    extract_district_from_address,
    reverse_geocode_coords,
    process_emulator_json,
)
from app.scraper.category_normalizer import normalize_category
from app.scraper.location_correction import get_corrected_location
from app.scraper.logger import scraper_logger, log
from app.scraper.constants import get_cities_to_scrape, CITIES, get_areas_for_district
from app.scraper.desktop_scraper import scrape_city as selenium_scrape_city, scrape_single_url
from app.scraper.playwright_scraper import scrape_city as playwright_scrape_city, preview_page
from app.scraper.api_scraper import scrape_city as api_scrape_city
from app.scraper.adb_location_search import automate_location_search, check_stop_flag

from app.api import categories as categories_api
from app.api import pincodes as pincodes_api

from . import service

router = APIRouter()


def _get_current_user(authorization: str = Header(None)) -> Optional[dict]:
    return service.get_current_user(authorization)


# ==========================================
# ADB DEVICE MANAGER
# ==========================================
class DeviceSelection(BaseModel):
    device_id: str


@router.get("/api/v1/adb/devices")
def get_all_adb_devices():
    adb_path = service.get_adb_path()
    if os.name == "nt" and "HD-Adb.exe" not in adb_path:
        for port in [5555, 5556, 5557, 5558, 5585, 5554]:
            try: subprocess.run(f'"{adb_path}" connect 127.0.0.1:{port}', shell=True, timeout=2)
            except: pass

    devices = service.get_adb_devices(adb_path)

    result = []
    for d in devices:
        model = d
        try:
            out = subprocess.check_output(f'"{adb_path}" -s {d} shell getprop ro.product.model', shell=True, text=True, timeout=2)
            if out.strip(): model = f"{out.strip()} ({d})"
        except: pass
        result.append({"id": d, "name": model})
    return {"devices": result}


@router.post("/api/v1/adb/device/select")
def select_adb_device(selection: DeviceSelection):
    config_path = os.path.join(settings.DATA_FOLDER, "active_device.txt")
    with open(config_path, "w") as f:
        f.write(selection.device_id.strip())
    return {"status": "success", "device_id": selection.device_id}


@router.get("/api/v1/adb/device/active")
def get_active_adb_device():
    config_path = os.path.join(settings.DATA_FOLDER, "active_device.txt")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            device = f.read().strip()
            if device:
                return {"device_id": device}
    return {"device_id": None}


# ==========================================
# UPLOAD LISTING (mobile app / extension ingestion)
# ==========================================
@router.post("/api/v1/upload-listing", status_code=201)
@router.post("/api/v1/upload-restaurant", status_code=201, deprecated=True)
def upload_listing(
    name: str = Form(...),
    phone: Optional[str] = Form(None),
    whatsapp: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    source_url: str = Form(...),
    category: Optional[str] = Form(None),
    opening_hours: Optional[str] = Form(None),
    district: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    menu_json: Optional[str] = Form(None),
    amenities_json: Optional[str] = Form(None),
    image_categories: Optional[str] = Form(None),
    image_urls_json: Optional[str] = Form(None),
    latitude: Optional[str] = Form(None),
    longitude: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: Optional[dict] = Depends(_get_current_user)
):
    try:
        # Hybrid Location Engine: Try Coordinate Reverse Geocoding first, fallback to address text parsing
        geo_info = reverse_geocode_coords(latitude, longitude)
        if geo_info:
            if geo_info.get("district"):
                district = geo_info["district"]
            cleaned_state = geo_info.get("state") or state or get_state_from_district(district or "")

            town_val = geo_info.get("town") or ""
            local_val = geo_info.get("local_area") or ""
            if local_val and town_val and local_val.lower() != town_val.lower():
                cleaned_place = f"{local_val}, {town_val}"
            else:
                cleaned_place = local_val or town_val
        else:
            addr_district = extract_district_from_address(address or "")
            if addr_district:
                district = addr_district

            cleaned_state = state or get_state_from_district(district or "")
            cleaned_place = extract_place_from_address(address or "", district or "")

        cleaned_cat = category or ""
        cleaned_sub = None

        if cleaned_cat:
            cleaned_cat, cleaned_sub = service.process_category_subcategory(cleaned_cat)

        cleaned_cat = detect_category_from_name(name, cleaned_cat)
        normalized_cat = normalize_category(cleaned_cat)

        # AUTO LOCATION CORRECTION
        if latitude and longitude:
            try:
                correction = get_corrected_location(latitude, longitude, current_district=district, current_place=cleaned_place)
                if correction.get("corrected"):
                    if correction.get("correct_district"):
                        district = correction["correct_district"]
                    if correction.get("correct_city"):
                        cleaned_place = correction["correct_city"]
                    if correction.get("correct_state"):
                        cleaned_state = correction["correct_state"]
            except Exception as e:
                print(f"Location correction failed for {name}: {e}")

        user_id = current_user["user_id"] if current_user else None
        with service.ingest_lock:
            existing_query = db.query(models.Listing).filter(models.Listing.name == name)
            if user_id:
                existing_query = existing_query.filter(models.Listing.user_id == user_id)
            existing = existing_query.first()

            if existing:
                listing = existing
                if phone: listing.phone = phone
                if whatsapp: listing.whatsapp = whatsapp
                if address: listing.address = address
                if opening_hours: listing.opening_hours = opening_hours
                if cleaned_cat: listing.category = cleaned_cat
                if cleaned_sub: listing.subcategory = cleaned_sub
                if normalized_cat: listing.normalized_category = normalized_cat
                if district: listing.district = district
                if cleaned_place: listing.place = cleaned_place
                if cleaned_state: listing.state = cleaned_state
                if latitude: listing.latitude = latitude
                if longitude: listing.longitude = longitude
                listing.scraped_at = datetime.datetime.utcnow()
                listing.menu_items.clear()
                listing.amenities.clear()
                if images or image_urls_json:
                    listing.images.clear()
            else:
                listing = models.Listing(
                    user_id=user_id,
                    name=name, phone=phone or "", whatsapp=whatsapp or "", address=address or "",
                    jd_url=source_url, category=cleaned_cat or "", subcategory=cleaned_sub, normalized_category=normalized_cat or "Other",
                    opening_hours=opening_hours or "",
                    district=district or "", place=cleaned_place or "", state=cleaned_state or "", latitude=latitude or "", longitude=longitude or ""
                )
                db.add(listing)
                db.flush()

            listing_id = listing.id

        if menu_json:
            try:
                for item in json.loads(menu_json):
                    db.add(models.MenuItem(listing_id=listing_id, name=str(item.get('name', '')), price=str(item.get('price', '0')), is_veg=bool(item.get('is_veg', True))))
            except Exception:
                pass

        if amenities_json:
            try:
                amenities_data = json.loads(amenities_json)
                if isinstance(amenities_data, dict):
                    for cat_name, values in amenities_data.items():
                        if isinstance(values, list):
                            for val in values:
                                db.add(models.Amenity(
                                    listing_id=listing_id,
                                    category=str(cat_name)[:100],
                                    value=str(val)[:200]
                                ))
            except Exception:
                pass

        categories = []
        if image_categories:
            try:
                categories = json.loads(image_categories)
            except Exception:
                pass

        if image_urls_json:
            try:
                urls_data = json.loads(image_urls_json)
                for i, item in enumerate(urls_data):
                    img_url = item.get('path')
                    cat = item.get('category', 'general')
                    if img_url:
                        db.add(models.ListingImage(
                            listing_id=listing_id,
                            image_path=img_url,
                            category=cat,
                            is_primary=(i == 0)
                        ))
            except Exception:
                pass
        else:
            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip()
            for i, img_file in enumerate(images):
                try:
                    if img_file and img_file.filename:
                        cat = categories[i] if i < len(categories) else "general"
                        safe_cat = "".join(c for c in cat if c.isalnum()).rstrip() or "general"
                        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                        filename = f"{safe_name}_{safe_cat}_{i}_{timestamp}.jpg"
                        image_path = os.path.join(service.UPLOAD_DIR, filename)
                        with open(image_path, "wb") as buffer:
                            shutil.copyfileobj(img_file.file, buffer)
                        db.add(models.ListingImage(listing_id=listing_id, image_path=image_path, category=cat, is_primary=(i == 0)))
                except Exception:
                    pass

        db.commit()
        return {"message": "Success", "listing_id": listing_id}

    except Exception as e:
        db.rollback()
        try:
            with open(service.ERROR_LOG_PATH, "a", encoding="utf-8") as f:
                import traceback
                f.write(f"=== {datetime.datetime.now()} ===\n")
                f.write(f"Error: {str(e)}\n")
                f.write(traceback.format_exc())
                f.write("\n")
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# TRIGGER SCRAPE (From Web UI)
# ==========================================
@router.post("/api/v1/scrape/stop")
def stop_scrape():
    service.scraping_in_progress = False
    service.scraping_started_at = None
    service.adb_search_in_progress = False

    flag_path = os.path.join(settings.DATA_FOLDER, "scrape_stop.flag")
    os.makedirs(os.path.dirname(flag_path), exist_ok=True)
    with open(flag_path, "w") as f:
        f.write("stop")
    log("🛑 Scraper stop requested by user (stop flag created).")
    return {"status": "stopped", "message": "Scraper stop signal sent."}


@router.post("/api/v1/scrape/reset")
def reset_scrape_lock():
    """Force-reset the scrape lock if a task got stuck"""
    was_locked = service.scraping_in_progress
    service.scraping_in_progress = False
    service.scraping_started_at = None
    service.adb_search_in_progress = False
    service.clear_stop_flag()
    return {"status": "reset", "was_locked": was_locked, "message": "Scrape lock cleared."}


@router.post("/api/v1/scrape/clear-history")
def clear_scrape_history():
    """Clears the resume history of scraped pincodes."""
    progress_file = os.path.join(settings.DATA_FOLDER, "scrape_progress.json")
    if os.path.exists(progress_file):
        try:
            os.remove(progress_file)
            log("🧹 Scrape progress history has been cleared.")
            return {"status": "cleared", "message": "Scrape history cleared successfully."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to clear history: {str(e)}"}
    return {"status": "ok", "message": "No history found to clear."}


@router.get("/api/v1/scrape/last-run")
def get_last_scrape_run():
    status_file = os.path.join(settings.DATA_FOLDER, "last_scrape_run.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r") as f:
                return json.load(f)
        except Exception as e:
            return {"status": "none", "error": str(e)}
    return {"status": "none"}


@router.post("/api/v1/scrape/continue")
def continue_last_scrape(background_tasks: BackgroundTasks = None):
    status_file = os.path.join(settings.DATA_FOLDER, "last_scrape_run.json")
    if not os.path.exists(status_file):
        raise HTTPException(status_code=404, detail="No previous scrape session found to continue.")

    try:
        with open(status_file, "r") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read scrape session data: {e}")

    district = data.get("district")
    category = data.get("category")
    max_pages = data.get("max_pages", 10)

    if not district or not category:
        raise HTTPException(status_code=400, detail="Incomplete previous scrape session data.")

    state_match = None
    for s_name, dists in CITIES.items():
        if district in dists:
            state_match = s_name
            break
    if not state_match:
        state_match = "Kerala"

    return trigger_scrape(
        state=state_match,
        district=district,
        main_cat=category,
        subcat="",
        max_limit=max_pages,
        start_page=1,
        fast_mode=False,
        engine="jwt_api",
        background_tasks=background_tasks
    )


@router.post("/api/v1/scrape")
def trigger_scrape(
    state: str,
    district: str,
    main_cat: str,
    subcat: str,
    max_limit: int = 10,
    start_page: int = 1,
    fast_mode: bool = False,
    engine: str = "playwright",
    background_tasks: BackgroundTasks = None
):
    service.clear_stop_flag()
    if service.scraping_in_progress:
        # Auto-expire lock if stuck for more than 30 minutes
        if service.scraping_started_at and (time.time() - service.scraping_started_at) > 1800:
            service.scraping_in_progress = False
            service.scraping_started_at = None
            log("⚠️ Scrape lock auto-expired after 30 minutes. Starting fresh.")
        else:
            raise HTTPException(status_code=400, detail="Scrape task is already in progress.")

    scraper_logger.clear()

    def run_sync_scrape():
        service.scraping_started_at = time.time()
        try:
            service.scraping_in_progress = True
            cities = get_cities_to_scrape(state, district)
            log(f"Orchestrator: Will scrape {len(cities)} cities.")

            progress_file = os.path.join(settings.DATA_FOLDER, "scrape_progress.json")
            progress_history = {}
            if os.path.exists(progress_file):
                try:
                    with open(progress_file, "r") as f:
                        progress_history = json.load(f)
                except Exception:
                    pass

            progress_key = f"{main_cat}_{subcat}"
            completed_cities = set(progress_history.get(progress_key, []))

            for city in cities:
                if city == "All": continue

                if city in completed_cities:
                    log(f"⏭️ Skipping {city}: already scraped for {progress_key}.")
                    continue

                log(f"--- Starting scrape for {city} ---")
                try:
                    if engine == "api":
                        api_scrape_city(city, main_cat, subcat, max_limit=max_limit, fast_mode=fast_mode, start_page=start_page, browser_type="chrome")
                    elif engine == "api_edge":
                        api_scrape_city(city, main_cat, subcat, max_limit=max_limit, fast_mode=fast_mode, start_page=start_page, browser_type="edge")
                    elif engine == "playwright":
                        playwright_scrape_city(city, main_cat, subcat, max_limit=max_limit, fast_mode=fast_mode, start_page=start_page, browser_type="chrome")
                    elif engine == "playwright_edge":
                        playwright_scrape_city(city, main_cat, subcat, max_limit=max_limit, fast_mode=fast_mode, start_page=start_page, browser_type="edge")
                    elif engine == "edge":
                        selenium_scrape_city(city, main_cat, subcat, max_limit=max_limit, fast_mode=fast_mode, start_page=start_page, browser_type="edge")
                    elif engine == "emulator":
                        search_cat = subcat if (subcat and subcat not in ["All", "—"]) else main_cat
                        areas = get_areas_for_district(city)
                        log(f"ADB Emulator: '{search_cat}' in '{city}' — {len(areas)} areas to search: {', '.join(areas)}")
                        automate_location_search(areas, search_cat, scrolls=max_limit, city=city)
                    elif engine == "jwt_api":
                        from jd_api_scraper import scrape_jwt_city
                        search_cat = subcat if (subcat and subcat not in ["All", "—"]) else main_cat
                        scrape_jwt_city(city, search_cat, pages=max_limit, limit=100, dry_run=False)
                    else:
                        selenium_scrape_city(city, main_cat, subcat, max_limit=max_limit, fast_mode=fast_mode, start_page=start_page, browser_type="chrome")

                    completed_cities.add(city)
                    progress_history[progress_key] = list(completed_cities)
                    try:
                        with open(progress_file, "w") as f:
                            json.dump(progress_history, f, indent=4)
                    except Exception as e:
                        log(f"Failed to save scrape progress: {e}", ok=False)

                except Exception as inner_e:
                    log(f"Error scraping {city}: {inner_e}", ok=False)
        except Exception as e:
            log(f"Scrape task failed: {e}", ok=False)
        finally:
            service.scraping_in_progress = False
            service.scraping_started_at = None
            log("Scrape task fully completed.")

    if background_tasks:
        background_tasks.add_task(run_sync_scrape)
        return {"status": "started", "message": "Scraping task started in the background."}
    else:
        threading.Thread(target=run_sync_scrape, daemon=True).start()
        return {"status": "started", "message": "Scraping task started."}


@router.post("/api/v1/scrape/cli")
async def trigger_cli_scrape(request: Request, background_tasks: BackgroundTasks):
    service.clear_stop_flag()
    if service.scraping_in_progress:
        raise HTTPException(status_code=400, detail="Scrape task is already in progress.")

    data = await request.json()
    cmd_str = data.get("command", "").strip()

    if not cmd_str.startswith("python jd_api_scraper.py") and not cmd_str.startswith("python3 jd_api_scraper.py") and not cmd_str.startswith("python scrape_"):
        raise HTTPException(status_code=400, detail="Only jd_api_scraper.py or scrape_*.py commands are allowed for safety.")

    actual_cmd = cmd_str
    if sys.platform == "win32":
        win_python = r"C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe"
        if os.path.exists(win_python):
            if cmd_str.startswith("python "):
                actual_cmd = cmd_str.replace("python ", f'"{win_python}" ', 1)
            elif cmd_str.startswith("python3 "):
                actual_cmd = cmd_str.replace("python3 ", f'"{win_python}" ', 1)

    scraper_logger.clear()

    def run_cli_scrape():
        import shlex
        service.scraping_started_at = time.time()
        service.scraping_in_progress = True

        log(f"💻 Starting CLI Scrape: {cmd_str}")
        def _is_stop_requested():
            flag_path = os.path.join(settings.DATA_FOLDER, "scrape_stop.flag")
            return os.path.exists(flag_path)

        try:
            process = subprocess.Popen(
                shlex.split(actual_cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace'
            )

            for line in iter(process.stdout.readline, ''):
                if line:
                    if _is_stop_requested():
                        log("⚠️ Stopping CLI scrape process as requested...")
                        process.terminate()
                        break
                    log(line.strip())

            process.stdout.close()
            return_code = process.wait()

            if _is_stop_requested():
                log("🛑 CLI Scrape stopped by user.")
            elif return_code == 0:
                log("✅ CLI Scrape completed successfully.")
            else:
                log(f"❌ CLI Scrape exited with code {return_code}", ok=False)

        except Exception as e:
            log(f"💥 Failed to execute CLI command: {e}", ok=False)
        finally:
            service.scraping_in_progress = False
            service.scraping_started_at = None

    background_tasks.add_task(run_cli_scrape)
    return {"status": "started", "message": "CLI command started."}


@router.get("/api/v1/scrape/status")
def get_scrape_status(last_idx: int = 0):
    new_logs, next_idx = scraper_logger.get_logs(last_idx)

    is_running = service.scraping_in_progress
    status_file = os.path.join(settings.DATA_FOLDER, "last_scrape_run.json")
    if not is_running and os.path.exists(status_file):
        try:
            with open(status_file, "r") as f:
                data = json.load(f)
                if data.get("status") == "running":
                    is_running = True
        except:
            pass

    running_for = None
    if is_running and service.scraping_started_at:
        running_for = int(time.time() - service.scraping_started_at)
    # Auto-expire after 30 min
    if service.scraping_in_progress and running_for and running_for > 1800:
        service.scraping_in_progress = False
        service.scraping_started_at = None
    return {
        "running": is_running,
        "running_for_seconds": running_for,
        "logs": new_logs,
        "next_idx": next_idx
    }


# ==========================================
# TRIGGER SINGLE URL SCRAPE (From Web UI)
# ==========================================
@router.post("/api/v1/scrape/single")
def trigger_single_scrape(url: str, fast_mode: bool = False, engine: str = "playwright", background_tasks: BackgroundTasks = None):
    service.clear_stop_flag()
    if service.scraping_in_progress:
        if service.scraping_started_at and (time.time() - service.scraping_started_at) > 1800:
            service.scraping_in_progress = False
            service.scraping_started_at = None
        else:
            raise HTTPException(status_code=400, detail="Scrape task is already in progress.")

    scraper_logger.clear()

    def run_single_scrape():
        service.scraping_started_at = time.time()
        try:
            service.scraping_in_progress = True
            browser_type = "edge" if engine in ["edge", "playwright_edge"] else "chrome"
            log(f"Starting single URL scrape for: {url} using {engine} ({browser_type})")
            scrape_single_url(url, engine=engine, browser_type=browser_type)
        except Exception as e:
            log(f"Single scrape failed: {e}", ok=False)
        finally:
            service.scraping_in_progress = False
            service.scraping_started_at = None
            log("Single scrape task completed.")

    if background_tasks:
        background_tasks.add_task(run_single_scrape)
        return {"status": "started", "message": "Single URL scraping task started in the background."}
    else:
        threading.Thread(target=run_single_scrape, daemon=True).start()
        return {"status": "started", "message": "Single URL scraping task started."}


# ==========================================
# LISTING COUNT — fetch total from JustDial
# ==========================================
@router.get("/api/v1/listing-count")
def get_listing_count(city: str, category: str):
    """Fetch total listing count from JustDial using Selenium"""
    try:
        import undetected_chromedriver as uc

        url = f"https://www.justdial.com/{city}/{category.replace(' ', '-')}"

        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-position=-32000,-32000")
        options.add_argument("--window-size=1280,720")

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        chrome_drivers_dir = os.path.join(project_root, "chrome_drivers")
        os.makedirs(chrome_drivers_dir, exist_ok=True)

        try:
            driver = uc.Chrome(options=options, use_subprocess=True, version_main=149, patcher_kwargs={"target_dir": chrome_drivers_dir})
        except Exception as e:
            print(f"⚠️ uc.Chrome with version_main=149 failed in listing-count: {e}. Trying autodetect...")
            try:
                driver = uc.Chrome(options=options, use_subprocess=True, patcher_kwargs={"target_dir": chrome_drivers_dir})
            except Exception as e2:
                print(f"❌ uc.Chrome autodetect failed in listing-count: {e2}. Falling back to standard Chrome...")
                from selenium import webdriver
                driver = webdriver.Chrome(options=options)
        try:
            driver.get(url)

            for _ in range(10):
                if 'nct-' in driver.current_url:
                    break
                time.sleep(1)

            time.sleep(3)

            from app.api.categories import _extract_count_from_html
            count = _extract_count_from_html(driver.page_source, category, None)

            if count:
                return {"count": count, "city": city, "category": category}
            return {"count": None}
        finally:
            try:
                driver.quit()
            except:
                pass
    except Exception as e:
        print(f"Failed to fetch count: {e}")
        return {"count": None}


# ==========================================
# PREVIEW PAGE — fetch names without saving
# ==========================================
@router.get("/api/v1/preview-page")
def get_preview_page(city: str, category: str, page: int = 1):
    """Preview names from a specific page without saving them."""
    try:
        results = preview_page(city, category, category, page)
        return {"status": "success", "data": results}
    except Exception as e:
        print(f"Preview failed: {e}")
        return {"status": "error", "message": str(e)}


# ==========================================
# EMULATOR JSON INGESTION
# ==========================================
@router.post("/api/v1/ingest-emulator-json")
async def ingest_emulator_json(request: Request, district: str = "Unknown", main_cat: str = ""):
    """
    Accepts raw JSON payload intercepted from JustDial mobile API (via HTTP Toolkit).
    Parses it and inserts it into the database, or compiles it to a file if Smart Scrape is active.
    """
    try:
        json_data = await request.json()

        if service.smart_scrape_state["active"]:
            file_path = service.smart_scrape_state["compile_file"]

            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        existing = json.load(f)
                    except:
                        existing = []
            else:
                existing = []

            if "json_data" in json_data:
                try:
                    raw_jd = json.loads(json_data["json_data"])
                    if "results" in raw_jd and isinstance(raw_jd["results"], dict) and "data" in raw_jd["results"]:
                        rows = raw_jd["results"]["data"]
                        for row in rows:
                            existing.append(row)
                except Exception as ex:
                    print("Error parsing smart scrape raw json:", ex)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing, f)

            return {"status": "success", "message": f"Appended to {file_path}", "count": len(existing)}

        success_count = process_emulator_json(json_data, district, main_cat=main_cat)

        return {"status": "success", "message": f"Successfully ingested {success_count} listings.", "count": success_count}
    except Exception as e:
        print(f"Emulator JSON Ingestion failed: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/v1/ingest-saved-folder")
def ingest_saved_folder(district: str = "Unknown", folder_path: str = r"c:\Users\PC\Desktop\JustDial_JSONs"):
    """
    Scans the specified folder on the desktop, reads all JSON files,
    combines them, and uploads them to the database.
    """
    try:
        if not os.path.exists(folder_path):
            return {"status": "error", "message": f"Folder does not exist: {folder_path}"}

        json_files = glob.glob(os.path.join(folder_path, "*.json"))
        if not json_files:
            return {"status": "success", "message": "No JSON files found in folder.", "count": 0}

        total_success = 0
        for file_path in json_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                count = process_emulator_json(data, district)
                total_success += count
            except Exception as file_err:
                print(f"Failed to ingest file {file_path}: {file_err}")

        return {
            "status": "success",
            "message": f"Successfully bulk uploaded {total_success} listings from {len(json_files)} files.",
            "count": total_success
        }
    except Exception as e:
        print(f"Bulk folder ingestion failed: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/v1/ingest-uploaded-file")
async def ingest_uploaded_file(
    file: UploadFile = File(...),
    district: str = Form("Unknown"),
    category: str = Form("Unknown")
):
    """
    Accepts an uploaded JSON file, parses it, and inserts it into the database under a specific category and district.
    """
    try:
        contents = await file.read()
        try:
            data = json.loads(contents.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON file format.")

        if isinstance(data, dict) and "json_data" not in data:
            payload = {
                "json_data": json.dumps(data),
                "district": district,
                "category": category
            }
        else:
            payload = data
            if isinstance(payload, dict):
                if district != "Unknown":
                    payload["district"] = district
                if category != "Unknown":
                    payload["category"] = category

        success_count = process_emulator_json(payload, district)
        return {"status": "success", "message": f"Successfully ingested {success_count} listings.", "count": success_count}
    except Exception as e:
        print(f"Uploaded file ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# TRIGGER ADB LOCATION SEARCH (Emulator Bridge)
# ==========================================
@router.post("/api/v1/adb/search")
def trigger_adb_search(
    location: str,
    category: str = "Restaurants",
    scrolls: int = 15,
    background_tasks: BackgroundTasks = None
):
    service.clear_stop_flag()
    if service.adb_search_in_progress:
        raise HTTPException(status_code=400, detail="ADB search is already in progress on the emulator.")

    scraper_logger.clear()

    def run_adb_search():
        try:
            service.adb_search_in_progress = True
            areas = get_areas_for_district(location)
            log(f"ADB Bridge: '{category}' in '{location}' — {len(areas)} areas: {', '.join(areas)}")
            automate_location_search(areas, category, scrolls, city=location)
            log("ADB Bridge: Completed search successfully.")
        except Exception as e:
            log(f"ADB Bridge: Search failed: {e}", ok=False)
        finally:
            service.adb_search_in_progress = False

    if background_tasks:
        background_tasks.add_task(run_adb_search)
        return {"status": "started", "message": "ADB location search started in the background."}
    else:
        threading.Thread(target=run_adb_search, daemon=True).start()
        return {"status": "started", "message": "ADB location search started."}


@router.get("/api/v1/adb/status")
def get_adb_status():
    return {"running": service.adb_search_in_progress}


@router.get("/api/v1/adb/screenshot")
def get_adb_screenshot():
    """Captures a screenshot from the active ADB emulator and returns it as a PNG file."""
    adb_path = service.get_adb_path()
    devices = service.get_adb_devices(adb_path)
    target = ""

    config_path = os.path.join(settings.DATA_FOLDER, "active_device.txt")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            saved_device = f.read().strip()
            if saved_device and saved_device in devices:
                target = f"-s {saved_device}"

    if not target and devices:
        target = f"-s {devices[0]}"

    img_path = "/tmp/emulator_screen.png" if os.name != "nt" else "emulator_screen.png"

    try:
        subprocess.check_call(f'"{adb_path}" {target} shell screencap -p /sdcard/screen.png', shell=True)
        subprocess.check_call(f'"{adb_path}" {target} pull /sdcard/screen.png {img_path}', shell=True)

        if os.path.exists(img_path):
            return FileResponse(img_path, media_type="image/png")
        else:
            raise HTTPException(status_code=500, detail="Failed to pull screenshot from emulator.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# TRIGGER SMART SCRAPE (Loop Pins & Subcategories)
# ==========================================
@router.post("/api/v1/adb/smart-scrape")
def trigger_smart_scrape(
    state: str,
    district: str,
    main_category: str,
    scrolls: int = 15,
    target_location: str = None,
    background_tasks: BackgroundTasks = None
):
    service.clear_stop_flag()
    if service.adb_search_in_progress:
        raise HTTPException(status_code=400, detail="ADB search is already in progress.")

    if target_location and target_location.strip():
        pincodes = [target_location.strip()]
    else:
        pincodes = pincodes_api.get_pincodes_for_district(district)

    if not pincodes:
        pincodes = [district]

    subcategories = service.SUBCATEGORIES_MAP.get(main_category, [])

    if not subcategories:
        cache_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", "category_cache.json")
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cat_data = json.load(f)
                mapping = {
                    "Automobile": "Automobiles",
                    "Beauty & Spa": "Beauty & Spas",
                    "Doctors": "Health & Medical",
                    "Hospitals": "Health & Medical",
                    "Hotels": "Hotels & Restaurants",
                    "Restaurants": "Hotels & Restaurants",
                    "Travel": "Travel & Tourism"
                }
                mapped_cat = mapping.get(main_category, main_category)
                if mapped_cat in cat_data:
                    subcategories = cat_data[mapped_cat].get("subcategories", [])
                    if main_category == "Restaurants" and subcategories:
                        subcategories = [s for s in subcategories if s != "Hotels"]
                    elif main_category == "Hotels" and subcategories:
                        subcategories = [s for s in subcategories if s != "Restaurants"]

    if not subcategories:
        subcategories = [main_category]

    compiled_folder = os.path.join(settings.DATA_FOLDER, "compiled_jsons")
    os.makedirs(compiled_folder, exist_ok=True)
    compile_file = os.path.join(compiled_folder, f"{district}_{main_category}_Compiled.json")

    with open(compile_file, "w", encoding="utf-8") as f:
        json.dump([], f)

    def run_smart_scrape():
        try:
            service.adb_search_in_progress = True
            service.smart_scrape_state["active"] = True
            service.smart_scrape_state["compile_file"] = compile_file
            service.smart_scrape_state["district"] = district
            service.smart_scrape_state["category"] = main_category

            scraper_logger.clear()
            log(f"SMART SCRAPE: Starting {district}. Found {len(pincodes)} locations and {len(subcategories)} subcategories.")

            for sub in subcategories:
                if check_stop_flag():
                    log("🛑 SMART SCRAPE: Stopped by user request. Exiting outer loop.")
                    break
                log(f"SMART SCRAPE: Processing subcategory -> {sub}")
                automate_location_search(pincodes, sub, scrolls, city=district)

            if check_stop_flag():
                log("🛑 SMART SCRAPE: Exited early due to user stop request.")
            else:
                log(f"SMART SCRAPE: Completed successfully! Compiled JSON saved to {compile_file}")

        except Exception as e:
            log(f"SMART SCRAPE: Failed with error: {e}", ok=False)
        finally:
            service.adb_search_in_progress = False
            service.smart_scrape_state["active"] = False

    if background_tasks:
        background_tasks.add_task(run_smart_scrape)
        return {"status": "started", "message": f"Smart scrape started for {district}. Subcategories: {len(subcategories)}"}
    else:
        threading.Thread(target=run_smart_scrape, daemon=True).start()
        return {"status": "started", "message": f"Smart scrape started for {district}. Subcategories: {len(subcategories)}"}


# ==========================================
# PROXY & ADB SCREEN/SCROLL/SCRCPY CONTROL
# ==========================================
@router.post("/api/v1/adb/proxy/start")
def api_start_proxy():
    try:
        if os.name == "nt":
            subprocess.run("taskkill /F /IM mitmdump.exe", shell=True, capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "mitmdump"], capture_output=True)
    except Exception:
        pass

    bluestacks_path = r"C:\Program Files\BlueStacks_nxt\HD-Player.exe"
    if os.name == "nt" and os.path.exists(bluestacks_path):
        try:
            tasklist_out = subprocess.check_output("tasklist /FI \"IMAGENAME eq HD-Player.exe\"", shell=True, text=True)
            if "HD-Player.exe" not in tasklist_out:
                subprocess.Popen([bluestacks_path])
                time.sleep(12)
        except Exception:
            pass

    adb_path = service.get_adb_path()

    mitmdump_path = "mitmdump"
    if os.name != "nt":
        for p in ["venv/bin/mitmdump", "mitmdump"]:
            if os.path.exists(p) or shutil.which(p):
                mitmdump_path = p
                break
    else:
        py_dir = os.path.dirname(sys.executable)
        path1 = os.path.join(py_dir, "mitmdump.exe")
        path2 = os.path.join(py_dir, "Scripts", "mitmdump.exe")
        if os.path.exists(path1):
            mitmdump_path = path1
        elif os.path.exists(path2):
            mitmdump_path = path2

    cmd = [mitmdump_path, "-s", "app/scraper/mitm_addon.py", "-p", "8089", "--set", "block_global=false"]
    try:
        log_file = open("mitmdump_live.log", "w", encoding="utf-8")
        subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            preexec_fn=os.setsid if os.name != "nt" else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start mitmdump: {str(e)}")

    server_ip = service.get_local_ip()
    devices = []

    for attempt in range(5):
        devices = service.get_adb_devices(adb_path)
        if devices:
            break
        time.sleep(3)

    if not devices:
        return {
            "status": "warning",
            "message": "Proxy started on port 8089, but BlueStacks took too long to respond. Please make sure BlueStacks is fully open and try clicking the button again."
        }

    configured = []
    errors = []
    for device in devices:
        adb_cmd = f'"{adb_path}" -s {device} shell settings put global http_proxy {server_ip}:8089'
        try:
            subprocess.check_call(adb_cmd, shell=True)
            configured.append(device)
        except Exception as e:
            errors.append(f"{device}: {str(e)}")

    if errors:
        return {
            "status": "warning",
            "message": f"Proxy started. Configured: {', '.join(configured)}. Failed: {', '.join(errors)}"
        }

    return {"status": "running", "message": f"Proxy started successfully and routed devices ({', '.join(configured)}) to {server_ip}:8089"}


@router.post("/api/v1/adb/proxy/stop")
def api_stop_proxy():
    try:
        if os.name == "nt":
            subprocess.run("taskkill /F /IM mitmdump.exe", shell=True, capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "mitmdump"], capture_output=True)
    except Exception:
        pass

    adb_path = service.get_adb_path()
    devices = service.get_adb_devices(adb_path)

    for device in devices:
        try:
            subprocess.run(f'"{adb_path}" -s {device} shell settings put global http_proxy :0', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(f'"{adb_path}" -s {device} shell settings delete global http_proxy', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(f'"{adb_path}" -s {device} shell settings delete global global_http_proxy_host', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(f'"{adb_path}" -s {device} shell settings delete global global_http_proxy_port', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    return {"status": "stopped", "message": "Proxy stopped and emulator proxy settings cleared."}


@router.get("/api/v1/adb/proxy/status")
def api_proxy_status():
    is_running = False
    if os.name != "nt":
        try:
            out = subprocess.run(["pgrep", "-f", "mitmdump"], capture_output=True, text=True)
            if out.returncode == 0 and out.stdout.strip():
                is_running = True
        except Exception:
            pass
    else:
        try:
            out = subprocess.check_output("tasklist /FI \"IMAGENAME eq mitmdump.exe\"", shell=True, text=True)
            if "mitmdump" in out:
                is_running = True
        except Exception:
            pass

    phone_proxy = "Unknown"
    try:
        adb_path = service.get_adb_path()
        devices = service.get_adb_devices(adb_path)
        if devices:
            device = devices[0]
            val = subprocess.check_output(f'"{adb_path}" -s {device} shell settings get global http_proxy', shell=True, text=True).strip()
            phone_proxy = val if val and val != "null" and val != ":0" else "None"
        else:
            phone_proxy = "Disconnected"
    except Exception:
        phone_proxy = "Disconnected"

    return {"running": is_running, "phone_proxy": phone_proxy}


@router.post("/api/v1/adb/scroll/start")
def api_start_scroll(interval: float = 3.0):
    if service._scroll_process and service._scroll_process.poll() is None:
        return {"status": "already_running", "message": "Auto-scroll is already running."}

    try:
        service._scroll_process = subprocess.Popen(
            [sys.executable, "-u", "-m", "app.scraper.adb_controller", "--interval", str(interval)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        return {"status": "started", "message": "Auto-scroll started successfully."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to start auto-scroll: {e}"}


@router.post("/api/v1/adb/scroll/stop")
def api_stop_scroll():
    if service._scroll_process and service._scroll_process.poll() is None:
        service._scroll_process.terminate()
        service._scroll_process = None
        return {"status": "stopped", "message": "Auto-scroll stopped successfully."}
    return {"status": "not_running", "message": "Auto-scroll is not running."}


@router.get("/api/v1/adb/scroll/status")
def api_scroll_status():
    is_running = service._scroll_process is not None and service._scroll_process.poll() is None
    return {"running": is_running}


@router.post("/api/v1/adb/scrcpy/start")
def start_scrcpy_mirror():
    adb_path = service.get_adb_path()
    if "scrcpy-win64" in adb_path:
        scrcpy_exe = adb_path.replace("adb.exe", "scrcpy.exe")
    else:
        scrcpy_exe = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scratch", "scrcpy", "scrcpy-win64-v4.0", "scrcpy.exe"))

    if not os.path.exists(scrcpy_exe):
        raise HTTPException(status_code=404, detail="scrcpy.exe not found.")

    devices = service.get_adb_devices(adb_path)
    target_device = ""

    config_path = os.path.join(settings.DATA_FOLDER, "active_device.txt")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            saved_device = f.read().strip()
            if saved_device and saved_device in devices:
                target_device = saved_device

    if not target_device and devices:
        target_device = devices[0]

    if not target_device:
        target_device = "100.110.105.12:5555"
        try:
            subprocess.run(f'"{adb_path}" connect {target_device}', shell=True, timeout=5)
        except Exception:
            pass

    try:
        cmd = f'"{scrcpy_exe}" -s {target_device} --tcpip={target_device}'
        subprocess.Popen(cmd, shell=True)
        return {"status": "success", "message": f"scrcpy started for {target_device}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/phone/screen")
def get_phone_screen_api():
    import io

    adb_path = service.get_adb_path()
    devices = service.get_adb_devices(adb_path)
    target = ""

    config_path = os.path.join(settings.DATA_FOLDER, "active_device.txt")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            saved_device = f.read().strip()
            if saved_device and saved_device in devices:
                target = f"-s {saved_device}"

    if not target and devices:
        target = f"-s {devices[0]}"

    if not target:
        target = "-s 100.110.105.12:5555"

    cmd = f'"{adb_path}" {target} shell screencap -p'
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode == 0:
        return StreamingResponse(io.BytesIO(result.stdout), media_type="image/png")
    return {"error": "Failed to capture screen or device offline"}


@router.get("/api/v1/phone/control")
def control_phone_api(action: str, x: int = None, y: int = None):
    adb_path = service.get_adb_path()
    devices = service.get_adb_devices(adb_path)
    target = ""

    config_path = os.path.join(settings.DATA_FOLDER, "active_device.txt")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            saved_device = f.read().strip()
            if saved_device and saved_device in devices:
                target = f"-s {saved_device}"

    if not target and devices:
        target = f"-s {devices[0]}"

    if not target:
        target = "-s 100.110.105.12:5555"

    cmd = ""
    if action == "tap" and x is not None and y is not None:
        cmd = f'"{adb_path}" {target} shell input tap {x} {y}'
    elif action == "scroll_down":
        cmd = f'"{adb_path}" {target} shell input swipe 500 1500 500 400 800'
    elif action == "scroll_up":
        cmd = f'"{adb_path}" {target} shell input swipe 500 400 500 1500 800'
    elif action == "back":
        cmd = f'"{adb_path}" {target} shell input keyevent 4'
    elif action == "home":
        cmd = f'"{adb_path}" {target} shell input keyevent 3'

    if cmd:
        subprocess.run(cmd, shell=True)
        return {"status": "ok", "action": action}
    return {"status": "error", "message": "Invalid action"}


@router.get("/api/v1/phone/size")
def get_phone_size_api():
    adb_path = service.get_adb_path()
    devices = service.get_adb_devices(adb_path)
    target = ""

    config_path = os.path.join(settings.DATA_FOLDER, "active_device.txt")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            saved_device = f.read().strip()
            if saved_device and saved_device in devices:
                target = f"-s {saved_device}"

    if not target and devices:
        target = f"-s {devices[0]}"

    if not target:
        target = "-s 100.110.105.12:5555"

    try:
        out = subprocess.check_output(f'"{adb_path}" {target} shell wm size', shell=True, text=True, timeout=3)
        if "size:" in out:
            size_str = out.split("size:")[-1].strip()
            w, h = map(int, size_str.split("x"))
            return {"width": w, "height": h}
    except Exception:
        pass
    return {"width": 1440, "height": 2960}


# ==========================================
# GOOGLE MAPS ADB SCRAPER
# ==========================================
gmaps_router = APIRouter(prefix="/api/v1/gmaps", tags=["gmaps"])
gmaps_in_progress = False


class GMapsRequest(BaseModel):
    query: str                    # e.g. "Hospitals in Abu Dhabi"
    max_results: int = 20
    scroll_count: int = 5
    district: str = ""
    upload_to_db: bool = True


@gmaps_router.post("/scrape")
def trigger_gmaps_scrape(request: GMapsRequest, background_tasks: BackgroundTasks = None):
    """Start a Google Maps ADB scrape for a given query."""
    global gmaps_in_progress
    if gmaps_in_progress:
        raise HTTPException(status_code=400, detail="Google Maps scrape already in progress.")

    scraper_logger.clear()

    def run():
        global gmaps_in_progress
        gmaps_in_progress = True
        try:
            from app.scraper.gmaps_scraper import scrape_gmaps, save_results, upload_to_db
            log(f"🗺️ Starting Google Maps scrape: {request.query}")
            results = scrape_gmaps(
                query=request.query,
                max_results=request.max_results,
                scroll_count=request.scroll_count
            )
            save_results(results)
            if request.upload_to_db:
                count = upload_to_db(results, district=request.district)
                log(f"✅ Uploaded {count} results to database.")
            else:
                log(f"✅ Scrape complete. {len(results['results'])} results (not uploaded).")
        except Exception as e:
            log(f"❌ Google Maps scrape failed: {e}", ok=False)
        finally:
            gmaps_in_progress = False
            log("🏁 Google Maps scrape task completed.")

    if background_tasks:
        background_tasks.add_task(run)
    else:
        threading.Thread(target=run, daemon=True).start()

    return {"status": "started", "message": f"Google Maps scrape started for: {request.query}"}


@gmaps_router.get("/status")
def get_gmaps_status(last_idx: int = 0):
    """Get current scrape status and logs."""
    new_logs, next_idx = scraper_logger.get_logs(last_idx)
    return {
        "running": gmaps_in_progress,
        "logs": new_logs,
        "next_idx": next_idx
    }


@gmaps_router.post("/reset")
def reset_gmaps_lock():
    """Force-reset the scrape lock if stuck."""
    global gmaps_in_progress
    was_locked = gmaps_in_progress
    gmaps_in_progress = False
    return {"status": "reset", "was_locked": was_locked}


@gmaps_router.get("/generate-intent")
def generate_intent(query: str):
    """
    Generate the ADB intent + extraction pipeline for a given query.
    Useful for debugging or manual execution.
    """
    encoded = query.replace(" ", "+")
    return {
        "query": query,
        "adb_intent": (
            f'adb shell am start -a android.intent.action.VIEW '
            f'-d "geo:0,0?q={encoded}" '
            f'-n com.google.android.apps.maps/com.google.android.maps.MapsActivity'
        ),
        "list_extraction": [
            "Wait 4 seconds for Maps to load",
            "adb shell uiautomator dump /sdcard/gmaps_list.xml",
            "adb pull /sdcard/gmaps_list.xml",
            "Parse clickable nodes for business names + tap coordinates",
            "Scroll: adb shell input swipe 540 1200 540 400 800",
            "Repeat until enough results collected"
        ],
        "detail_extraction": [
            "For each list item:",
            "  adb shell input tap <x> <y>   # open detail page",
            "  Wait 3 seconds",
            "  adb shell uiautomator dump /sdcard/gmaps_detail.xml",
            "  adb pull /sdcard/gmaps_detail.xml",
            "  Parse: name, address, phone, website, rating, reviews, hours",
            "  adb shell dumpsys activity | grep geo:   # get coordinates",
            "  adb shell input keyevent 4               # go back"
        ],
        "expected_json": {
            "query": query,
            "results": [
                {
                    "name": "",
                    "address": "",
                    "phone": "",
                    "website": "",
                    "rating": "",
                    "reviews": "",
                    "hours": "",
                    "category": "",
                    "latitude": "",
                    "longitude": ""
                }
            ]
        }
    }


router.include_router(gmaps_router)


# ==========================================
# SIMPLE ONE-SHOT GOOGLE MAPS IMAGE SCRAPER
# ==========================================
import re
import asyncio


class SimpleScrapeRequest(BaseModel):
    url: str
    max_images: int = 30


def _canonical_img_url(url: str) -> str:
    return re.sub(r"=(w\d+|h\d+|s\d+|w\d+-h\d+).*$", "", url)


def _is_valid_img(url: str) -> bool:
    if "/a/" in url or "/a-/" in url:
        return False
    bad_sizes = ["w32-h32", "w48-h48", "w64-h64", "w20-h20",
                 "w34-h34", "w16-h16", "w24-h24", "w40-h40", "w56-h56"]
    return not any(sz in url for sz in bad_sizes)


async def _do_simple_scrape(url: str, max_images: int) -> dict:
    from playwright.async_api import async_playwright

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

        try:
            await page.wait_for_function(
                "() => { var el = document.querySelector('h1.DUwDvf'); return el && el.innerText.trim().length > 0; }",
                timeout=10000
            )
        except Exception:
            await page.wait_for_timeout(5000)

        await page.wait_for_timeout(1500)

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

        all_imgs = await page.evaluate("""
            () => {
                let out = new Set();
                document.querySelectorAll('img,[data-src]').forEach(el => {
                    let s = el.getAttribute('data-src') || el.src || '';
                    if (s && (s.includes('googleusercontent') || s.includes('ggpht'))) out.add(s);
                });
                document.querySelectorAll('[style*="googleusercontent"],[style*="ggpht"]').forEach(el => {
                    let style = el.getAttribute('style') || '';
                    for (let m of style.matchAll(/url\\("?([^"')]+(?:googleusercontent|ggpht)[^"')]+)"?\\)/g)) {
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
            if not _is_valid_img(src):
                continue
            base = _canonical_img_url(src)
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


@router.post("/api/v1/simple-scrape")
def simple_scrape(request: SimpleScrapeRequest):
    """Scrape a Google Maps place URL and return images immediately."""
    try:
        result = asyncio.run(_do_simple_scrape(request.url, request.max_images))
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


# ── Existing category/pincode routers, unchanged (see module docstring) ──────
router.include_router(categories_api.router)
router.include_router(pincodes_api.router)
