import sys
import os
import shutil
import datetime
import json
import traceback
import subprocess
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session, selectinload
from typing import Optional, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.database import get_db
from app import models
from config import settings
from app_config import CONFIG as APP_CONFIG

# Ensure data folder exists
os.makedirs(settings.DATA_FOLDER, exist_ok=True)

# Get absolute paths for error log and images
ERROR_LOG_PATH = os.path.join(settings.DATA_FOLDER, "upload_error_log.txt")
UPLOAD_DIR = os.path.join(settings.DATA_FOLDER, "uploaded_images")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==========================================
# ROUTER INITIALIZATION
# ==========================================
router = APIRouter()

# ==========================================
# 1. UPLOAD RESTAURANT (Existing)
# ==========================================
@router.post("/upload-restaurant", status_code=201)
def upload_restaurant(
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
    db: Session = Depends(get_db)
):
    try:
        existing = db.query(models.Restaurant).filter(models.Restaurant.name == name).first()
        
        if existing:
            restaurant = existing
            # Only overwrite fields if new value is provided (never blank out existing data)
            if phone: restaurant.phone = phone
            if whatsapp: restaurant.whatsapp = whatsapp
            if address: restaurant.address = address
            if opening_hours: restaurant.opening_hours = opening_hours
            if category: restaurant.category = category
            if district: restaurant.district = district
            if state: restaurant.state = state
            if latitude: restaurant.latitude = latitude
            if longitude: restaurant.longitude = longitude
            restaurant.scraped_at = datetime.datetime.utcnow()
            # Only clear menus/amenities to re-enrich — NOT images (keep mobile API images)
            restaurant.menu_items.clear()
            restaurant.amenities.clear()
            # Only clear images if new ones are being uploaded (don't wipe mobile API images)
            if images or image_urls_json:
                restaurant.images.clear()
        else:
            restaurant = models.Restaurant(
                name=name, phone=phone or "", whatsapp=whatsapp or "", address=address or "",
                jd_url=source_url, category=category or "", opening_hours=opening_hours or "",
                district=district or "", state=state or "", latitude=latitude or "", longitude=longitude or ""
            )
            db.add(restaurant)
            db.flush()
            
        restaurant_id = restaurant.id

        # Add menu items (robustly
        if menu_json:
            try:
                for item in json.loads(menu_json):
                    db.add(models.MenuItem(restaurant_id=restaurant_id, name=str(item.get('name', '')), price=str(item.get('price', '0')), is_veg=bool(item.get('is_veg', True))))
            except Exception as menu_e:
                pass  # Ignore menu errors, still save other data

        # Add amenities robustly
        if amenities_json:
            try:
                amenities_data = json.loads(amenities_json)
                if isinstance(amenities_data, dict):
                    for category, values in amenities_data.items():
                        if isinstance(values, list):
                            for val in values:
                                db.add(models.Amenity(restaurant_id=restaurant_id, category=str(category), value=str(val)))
            except Exception as amenity_e:
                pass  # Ignore amenities errors

        # Process images robustly
        categories = []
        if image_categories:
            try:
                categories = json.loads(image_categories)
            except Exception as cat_e:
                pass  # Use empty list

        if image_urls_json:
            try:
                urls_data = json.loads(image_urls_json)
                for i, item in enumerate(urls_data):
                    img_url = item.get('path')
                    cat = item.get('category', 'general')
                    if img_url:
                        db.add(models.RestaurantImage(
                            restaurant_id=restaurant_id,
                            image_path=img_url,
                            category=cat,
                            is_primary=(i == 0)
                        ))
            except Exception as e:
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
                        image_path = os.path.join(UPLOAD_DIR, filename)
                        with open(image_path, "wb") as buffer:
                            shutil.copyfileobj(img_file.file, buffer)
                        db.add(models.RestaurantImage(restaurant_id=restaurant_id, image_path=image_path, category=cat, is_primary=(i == 0)))
                except Exception as img_e:
                    pass  # Skip image fails, still save rest

        db.commit()
        return {"message": "Success", "restaurant_id": restaurant_id}

    except Exception as e:
        db.rollback()
        # Log detailed error to file
        try:
            with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"=== {datetime.datetime.now()} ===\n")
                f.write(f"Error: {str(e)}\n")
                f.write(traceback.format_exc())
                f.write("\n")
        except:
            pass  # Ignore if logging fails
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. GET ALL RESTAURANTS (Existing)
# ==========================================
@router.get("/restaurants")
def get_restaurants(
    page: int = 1, 
    limit: int = 10000, 
    district: Optional[str] = None, 
    state: Optional[str] = None, 
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Restaurant)
    
    if state:
        query = query.filter(models.Restaurant.state == state)
    if district:
        query = query.filter(models.Restaurant.district == district)
    if category:
        query = query.filter(models.Restaurant.category == category)
        
    total_count = query.count()
    
    restaurants = query.options(
        selectinload(models.Restaurant.images),
        selectinload(models.Restaurant.menu_items),
        selectinload(models.Restaurant.amenities)
    ).order_by(models.Restaurant.id.desc()).offset((page - 1) * limit).limit(limit).all()
    
    result = []
    for r in restaurants:
        primary_img = next((img.image_path for img in r.images if img.is_primary), None)
        if not primary_img and r.images: primary_img = r.images[0].image_path
            
        menu_list = [{"name": m.name, "price": m.price, "is_veg": m.is_veg} for m in r.menu_items]
        amenities_list = [{"category": a.category, "value": a.value} for a in r.amenities]
        images_list = [{"path": img.image_path, "category": img.category or "general"} for img in r.images]
        
        result.append({
            "id": r.id, "name": r.name, "phone": r.phone, "whatsapp": r.whatsapp, "address": r.address,
            "jd_url": r.jd_url, "category": r.category, "opening_hours": r.opening_hours,
            "district": r.district, "state": r.state,
            "latitude": r.latitude, "longitude": r.longitude,
            "image_path": primary_img, "menu_items": menu_list, "amenities": amenities_list, "images": images_list
        })
        
    return {
        "data": result,
        "total_count": total_count,
        "page": page,
        "limit": limit
    }

# ==========================================
# 3. NEW: GET STATS (For the Dashboard)
# ==========================================
@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_restaurants = db.query(models.Restaurant).count()
    total_images = db.query(models.RestaurantImage).count()
    total_menu_items = db.query(models.MenuItem).count()
    return {
        "total_restaurants": total_restaurants,
        "total_images": total_images,
        "total_menu_items": total_menu_items
    }

# ==========================================
# 4. NEW: DELETE DUPLICATES
# ==========================================
@router.post("/delete-duplicates")
def delete_duplicates(db: Session = Depends(get_db)):
    restaurants = db.query(models.Restaurant).all()
    seen = {}
    duplicates = []
    
    for r in restaurants:
        # Create a unique key based on Name and Phone
        key = (r.name.strip().lower(), r.phone.strip() if r.phone else "")
        if key in seen:
            duplicates.append(r)
        else:
            seen[key] = r
            
    for d in duplicates:
        db.delete(d)
        
    db.commit()
    return {"deleted": len(duplicates)}

# ==========================================
# 5. NEW: DELETE SINGLE RESTAURANT
# ==========================================
@router.delete("/restaurant/{restaurant_id}")
def delete_restaurant(restaurant_id: int, delete_images: bool = False, db: Session = Depends(get_db)):
    restaurant = db.query(models.Restaurant).filter(models.Restaurant.id == restaurant_id).first()
    
    if not restaurant:
        raise HTTPException(status_code=404, detail=f"Restaurant with ID {restaurant_id} not found")
    
    # Collect images to delete if needed
    image_paths = []
    if delete_images:
        for img in restaurant.images:
            if img.image_path and os.path.exists(img.image_path):
                image_paths.append(img.image_path)
    
    # Delete from DB (SQLAlchemy handles cascading delete for related items)
    db.delete(restaurant)
    db.commit()
    
    # Delete images from file system (optimized)
    if delete_images and image_paths:
        import threading
        def delete_files():
            for img_path in image_paths:
                try:
                    os.remove(img_path)
                except Exception:
                    pass
        threading.Thread(target=delete_files).start()  # Delete files in background to reduce lag
    
    return {"status": "success", "deleted_id": restaurant_id}

# ==========================================
# 6. NEW: CLEAR ALL DATA (Danger Zone)
# ==========================================
@router.post("/clear-all")
def clear_all(db: Session = Depends(get_db)):
    # First collect all image paths
    images = db.query(models.RestaurantImage).all()
    image_paths = [img.image_path for img in images if img.image_path and os.path.exists(img.image_path)]
    
    # Delete from DB
    db.query(models.MenuItem).delete()
    db.query(models.Amenity).delete()
    db.query(models.RestaurantImage).delete()
    db.query(models.Restaurant).delete()
    db.commit()
    
    # Delete images in background to reduce lag
    if image_paths:
        import threading
        def delete_all_files():
            for img_path in image_paths:
                try:
                    os.remove(img_path)
                except Exception:
                    pass
        threading.Thread(target=delete_all_files).start()
    
    return {"status": "success"}

# ==========================================
# 7. TRIGGER SCRAPE (From Web UI)
# ==========================================
from app.scraper.desktop_scraper import scrape_city as selenium_scrape_city
from app.scraper.playwright_scraper import scrape_city as playwright_scrape_city
from app.scraper.api_scraper import scrape_city as api_scrape_city
from app.scraper.constants import get_cities_to_scrape
from app.scraper.logger import scraper_logger, log

scraping_in_progress = False
scraping_started_at = None  # Track when scraping started

@router.post("/scrape/reset")
def reset_scrape_lock():
    """Force-reset the scrape lock if a task got stuck"""
    global scraping_in_progress, scraping_started_at
    was_locked = scraping_in_progress
    scraping_in_progress = False
    scraping_started_at = None
    return {"status": "reset", "was_locked": was_locked, "message": "Scrape lock cleared."}

@router.post("/scrape")
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
    global scraping_in_progress, scraping_started_at
    if scraping_in_progress:
        # Auto-expire lock if stuck for more than 30 minutes
        import time as _time
        if scraping_started_at and (_time.time() - scraping_started_at) > 1800:
            scraping_in_progress = False
            scraping_started_at = None
            log("⚠️ Scrape lock auto-expired after 30 minutes. Starting fresh.")
        else:
            raise HTTPException(status_code=400, detail="Scrape task is already in progress.")
        
    scraper_logger.clear()
        
    def run_sync_scrape():
        global scraping_in_progress, scraping_started_at
        import time as _time
        scraping_started_at = _time.time()
        try:
            scraping_in_progress = True
            cities = get_cities_to_scrape(state, district)
            log(f"Orchestrator: Will scrape {len(cities)} cities.")
            for city in cities:
                if city == "All": continue
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
                        from app.scraper.adb_location_search import automate_location_search
                        search_cat = subcat if (subcat and subcat not in ["All", "—"]) else main_cat
                        log(f"ADB Emulator: Starting search for '{search_cat}' in '{city}' with {max_limit} scrolls.")
                        automate_location_search([city], search_cat, scrolls=max_limit)
                    else:
                        selenium_scrape_city(city, main_cat, subcat, max_limit=max_limit, fast_mode=fast_mode, start_page=start_page, browser_type="chrome")
                except Exception as inner_e:
                    log(f"Error scraping {city}: {inner_e}", ok=False)
        except Exception as e:
            log(f"Scrape task failed: {e}", ok=False)
        finally:
            scraping_in_progress = False
            scraping_started_at = None
            log("Scrape task fully completed.")
            
    if background_tasks:
        background_tasks.add_task(run_sync_scrape)
        return {"status": "started", "message": "Scraping task started in the background."}
    else:
        import threading
        threading.Thread(target=run_sync_scrape, daemon=True).start()
        return {"status": "started", "message": "Scraping task started."}

@router.get("/scrape/status")
def get_scrape_status(last_idx: int = 0):
    global scraping_in_progress, scraping_started_at
    import time as _time
    new_logs, next_idx = scraper_logger.get_logs(last_idx)
    running_for = None
    if scraping_in_progress and scraping_started_at:
        running_for = int(_time.time() - scraping_started_at)
    # Auto-expire after 30 min
    if scraping_in_progress and running_for and running_for > 1800:
        scraping_in_progress = False
        scraping_started_at = None
    return {
        "running": scraping_in_progress,
        "running_for_seconds": running_for,
        "logs": new_logs,
        "next_idx": next_idx
    }

# ==========================================
# 8. TRIGGER SINGLE URL SCRAPE (From Web UI)
# ==========================================
from app.scraper.desktop_scraper import scrape_single_url

@router.post("/scrape/single")
def trigger_single_scrape(url: str, fast_mode: bool = False, engine: str = "playwright", background_tasks: BackgroundTasks = None):
    global scraping_in_progress, scraping_started_at
    if scraping_in_progress:
        import time as _time
        if scraping_started_at and (_time.time() - scraping_started_at) > 1800:
            scraping_in_progress = False
            scraping_started_at = None
        else:
            raise HTTPException(status_code=400, detail="Scrape task is already in progress.")
        
    scraper_logger.clear()
        
    def run_single_scrape():
        global scraping_in_progress, scraping_started_at
        import time as _time
        scraping_started_at = _time.time()
        try:
            scraping_in_progress = True
            browser_type = "edge" if engine in ["edge", "playwright_edge"] else "chrome"
            log(f"Starting single URL scrape for: {url} using {engine} ({browser_type})")
            scrape_single_url(url, engine=engine, browser_type=browser_type)
        except Exception as e:
            log(f"Single scrape failed: {e}", ok=False)
        finally:
            scraping_in_progress = False
            scraping_started_at = None
            log("Single scrape task completed.")

    if background_tasks:
        background_tasks.add_task(run_single_scrape)
        return {"status": "started", "message": "Single URL scraping task started in the background."}
    else:
        import threading
        threading.Thread(target=run_single_scrape, daemon=True).start()
        return {"status": "started", "message": "Single URL scraping task started."}

# ==========================================
# LISTING COUNT — fetch total from JustDial
# ==========================================
@router.get("/listing-count")
def get_listing_count(city: str, category: str):
    """Fetch total listing count from JustDial using Selenium"""
    try:
        import undetected_chromedriver as uc
        from bs4 import BeautifulSoup

        url = f"https://www.justdial.com/{city}/{category.replace(' ', '-')}"

        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-position=-32000,-32000") # Off-screen magic
        options.add_argument("--window-size=1280,720")

        # Define chrome_drivers_dir
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
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
            
            # Wait up to 10 seconds for the redirect to the nct- category page
            import time
            for _ in range(10):
                if 'nct-' in driver.current_url:
                    break
                time.sleep(1)
            
            time.sleep(3)  # wait for JS to render after redirect
            
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
from app.scraper.playwright_scraper import preview_page

@router.get("/preview-page")
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
smart_scrape_state = {
    "active": False,
    "compile_file": "",
    "district": "",
    "category": ""
}

@router.post("/ingest-emulator-json")
async def ingest_emulator_json(request: Request, district: str = "Unknown"):
    """
    Accepts raw JSON payload intercepted from JustDial mobile API (via HTTP Toolkit).
    Parses it and inserts it into the database, or compiles it to a file if Smart Scrape is active.
    """
    try:
        from app.scraper.emulator_parser import process_emulator_json
        import os, json
        
        json_data = await request.json()
        
        if smart_scrape_state["active"]:
            # SMART SCRAPE MODE: Append to file instead of DB to compile small JSONs
            file_path = smart_scrape_state["compile_file"]
            
            # Read existing
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        existing = json.load(f)
                    except:
                        existing = []
            else:
                existing = []
                
            # Filter the new data to NOT include base64 images (just keep native JD JSON rows)
            if "json_data" in json_data:
                try:
                    raw_jd = json.loads(json_data["json_data"])
                    if "results" in raw_jd and isinstance(raw_jd["results"], dict) and "data" in raw_jd["results"]:
                        rows = raw_jd["results"]["data"]
                        for row in rows:
                            # Safely extract image URLs if needed, but JD usually only sends URLs anyway.
                            # Just append the raw row to compile them!
                            existing.append(row)
                except Exception as ex:
                    print("Error parsing smart scrape raw json:", ex)
            
            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing, f)
            
            return {"status": "success", "message": f"Appended to {file_path}", "count": len(existing)}

        # Normal DB ingestion
        success_count = process_emulator_json(json_data, district)
        
        return {"status": "success", "message": f"Successfully ingested {success_count} restaurants.", "count": success_count}
    except Exception as e:
        print(f"Emulator JSON Ingestion failed: {e}")
        return {"status": "error", "message": str(e)}

@router.post("/ingest-saved-folder")
def ingest_saved_folder(district: str = "Unknown", folder_path: str = r"c:\Users\PC\Desktop\JustDial_JSONs"):
    """
    Scans the specified folder on the desktop, reads all JSON files,
    combines them, and uploads them to the database.
    """
    try:
        from app.scraper.emulator_parser import process_emulator_json
        import glob
        
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
                # Optional: Delete or rename file after successful ingestion so it isn't ingested again
                # os.rename(file_path, file_path + ".ingested")
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

# ==========================================
# 9. TRIGGER ADB LOCATION SEARCH (Emulator Bridge)
# ==========================================
from app.scraper.adb_location_search import automate_location_search

adb_search_in_progress = False

@router.post("/adb/search")
def trigger_adb_search(
    location: str,
    category: str = "Restaurants",
    scrolls: int = 15,
    background_tasks: BackgroundTasks = None
):
    global adb_search_in_progress
    if adb_search_in_progress:
        raise HTTPException(status_code=400, detail="ADB search is already in progress on the emulator.")
        
    # Clear logs so the user sees fresh logs for their emulator run
    scraper_logger.clear()
        
    def run_adb_search():
        global adb_search_in_progress
        try:
            adb_search_in_progress = True
            log(f"ADB Bridge: Starting emulator search for category '{category}' in location '{location}' with {scrolls} scrolls.")
            automate_location_search([location], category, scrolls)
            log("ADB Bridge: Completed search successfully.")
        except Exception as e:
            log(f"ADB Bridge: Search failed: {e}", ok=False)
        finally:
            adb_search_in_progress = False
            
    if background_tasks:
        background_tasks.add_task(run_adb_search)
        return {"status": "started", "message": "ADB location search started in the background."}
    else:
        import threading
        threading.Thread(target=run_adb_search, daemon=True).start()
        return {"status": "started", "message": "ADB location search started."}

@router.get("/adb/status")
def get_adb_status():
    global adb_search_in_progress
    return {"running": adb_search_in_progress}

@router.get("/adb/screenshot")
def get_adb_screenshot():
    """Captures a screenshot from the active ADB emulator and returns it as a PNG file."""
    import subprocess
    import os
    from fastapi.responses import FileResponse
    
    if os.name == "nt":
        adb_path = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
        target = ""
    else:
        adb_path = "adb"
        target = "-s 100.97.77.69:5555"
        
    img_path = "/tmp/emulator_screen.png" if os.name != "nt" else "emulator_screen.png"
    
    try:
        # Capture screenshot to emulator SD card
        subprocess.check_call(f'"{adb_path}" {target} shell screencap -p /sdcard/screen.png', shell=True)
        # Pull to local server directory
        subprocess.check_call(f'"{adb_path}" {target} pull /sdcard/screen.png {img_path}', shell=True)
        
        if os.path.exists(img_path):
            return FileResponse(img_path, media_type="image/png")
        else:
            raise HTTPException(status_code=500, detail="Failed to pull screenshot from emulator.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 10. TRIGGER SMART SCRAPE (Loop Pins & Subcategories)
# ==========================================
SUBCATEGORIES_MAP = {
    "Home Services": ["Plumbers", "Electricians", "Carpenters", "Painters", "Cleaners"],
    "Restaurants": ["Fast Food", "Fine Dining", "Cafes", "Bakeries", "Chinese"],
    "Hospitals": ["Multi-Specialty", "Dental", "Eye Care", "Orthopedic", "Pediatric"],
    "Hotels": ["Budget", "3 Star", "4 Star", "5 Star", "Resorts"],
    "Education": ["Schools", "Colleges", "Coaching", "Play Schools", "Music Classes"],
    "Real Estate": ["Agents", "Builders", "PG / Hostels", "Rentals"],
    "Automobile": ["Car Dealers", "Bike Dealers", "Service Centres", "Spare Parts"],
    "Beauty & Spa": ["Salons", "Spas", "Nail Art", "Tattoo"],
    "Doctors": ["General Physician", "Cardiologist", "Dermatologist", "Gynaecologist"],
    "Travel": ["Travel Agents", "Cab Services", "Tour Operators", "Airlines"],
    "Home Decor": ["Furnitures", "Furnishing", "Lamps-Lighting", "Kitchen-Dining", "Interior-Designers"]
}

@router.post("/adb/smart-scrape")
def trigger_smart_scrape(
    state: str,
    district: str,
    main_category: str,
    scrolls: int = 15,
    target_location: str = None,
    background_tasks: BackgroundTasks = None
):
    global adb_search_in_progress, smart_scrape_state
    if adb_search_in_progress:
        raise HTTPException(status_code=400, detail="ADB search is already in progress.")
        
    if target_location and target_location.strip():
        pincodes = [target_location.strip()]
    else:
        from app.api.pincodes import get_pincodes_for_district
        pincodes = get_pincodes_for_district(district)
    
    # Fallback to District name if no PINs found
    if not pincodes:
        pincodes = [district]
        
    # Get subcategories
    subcategories = SUBCATEGORIES_MAP.get(main_category, [])
    
    if not subcategories:
        # Fallback to category_cache.json
        import os, json
        cache_file = os.path.join(os.path.dirname(__file__), "..", "..", "category_cache.json")
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cat_data = json.load(f)
                # Apply mapping translation if needed
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
                    # If we mapped Restaurants, filter out "Hotels" or non-restaurant subcategories
                    if main_category == "Restaurants" and subcategories:
                        subcategories = [s for s in subcategories if s != "Hotels"]
                    elif main_category == "Hotels" and subcategories:
                        subcategories = [s for s in subcategories if s != "Restaurants"]
                        
    if not subcategories:
        # If none found, just search the main category
        subcategories = [main_category]
        
    compiled_folder = os.path.join(os.path.dirname(__file__), "..", "..", "data", "compiled_jsons")
    os.makedirs(compiled_folder, exist_ok=True)
    compile_file = os.path.join(compiled_folder, f"{district}_{main_category}_Compiled.json")
    
    # Initialize empty compiled file
    with open(compile_file, "w", encoding="utf-8") as f:
        json.dump([], f)
        
    def run_smart_scrape():
        global adb_search_in_progress, smart_scrape_state
        try:
            adb_search_in_progress = True
            smart_scrape_state["active"] = True
            smart_scrape_state["compile_file"] = compile_file
            smart_scrape_state["district"] = district
            smart_scrape_state["category"] = main_category
            
            scraper_logger.clear()
            log(f"SMART SCRAPE: Starting {district}. Found {len(pincodes)} locations and {len(subcategories)} subcategories.")
            
            for sub in subcategories:
                log(f"SMART SCRAPE: Processing subcategory -> {sub}")
                automate_location_search(pincodes, sub, scrolls)
                
            log(f"SMART SCRAPE: Completed successfully! Compiled JSON saved to {compile_file}")
            
        except Exception as e:
            log(f"SMART SCRAPE: Failed with error: {e}", ok=False)
        finally:
            adb_search_in_progress = False
            smart_scrape_state["active"] = False
            
    if background_tasks:
        background_tasks.add_task(run_smart_scrape)
        return {"status": "started", "message": f"Smart scrape started for {district}. Subcategories: {len(subcategories)}"}
    else:
        import threading
        threading.Thread(target=run_smart_scrape, daemon=True).start()
        return {"status": "started", "message": f"Smart scrape started for {district}. Subcategories: {len(subcategories)}"}

# ==========================================
# 11. PROXY & COMPILED JSON MANAGER ENDPOINTS
# ==========================================

def _get_local_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def _get_adb_devices(adb_path):
    try:
        if os.name != "nt":
            # On remote Linux server, connect to desktop emulator over Tailscale VPN
            try:
                subprocess.run(f'"{adb_path}" connect 100.97.77.69:5555', shell=True, timeout=8)
            except Exception:
                pass
        out = subprocess.check_output(f'"{adb_path}" devices', shell=True, text=True)
        devices = []
        for line in out.strip().splitlines()[1:]:
            if line.strip() and "device" in line and "devices" not in line:
                devices.append(line.split()[0])
        return devices
    except Exception:
        return []

@router.post("/adb/proxy/start")
def api_start_proxy():
    # 1. Kill any existing mitmdump to free up port 8089
    try:
        if os.name == "nt":
            subprocess.run("taskkill /F /IM mitmdump.exe", shell=True, capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "mitmdump"], capture_output=True)
    except Exception:
        pass
        
    # 2. Check and Launch BlueStacks if closed
    bluestacks_path = r"C:\Program Files\BlueStacks_nxt\HD-Player.exe"
    if os.name == "nt" and os.path.exists(bluestacks_path):
        try:
            tasklist_out = subprocess.check_output("tasklist /FI \"IMAGENAME eq HD-Player.exe\"", shell=True, text=True)
            if "HD-Player.exe" not in tasklist_out:
                subprocess.Popen([bluestacks_path])
                time.sleep(12) # Wait for it to boot up
        except Exception:
            pass

    # 3. Start mitmdump
    adb_path = "adb" if os.name != "nt" else os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    mitmdump_path = "venv/bin/mitmdump" if os.name != "nt" else "venv/Scripts/mitmdump.exe"
    if not os.path.exists(mitmdump_path):
        mitmdump_path = "mitmdump" # fallback to path
        
    cmd = [mitmdump_path, "-s", "app/scraper/mitm_addon.py", "-p", "8089"]
    try:
        # Run it in background and redirect output to a log file
        log_file = open("mitmdump_live.log", "w", encoding="utf-8")
        subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            preexec_fn=os.setsid if os.name != "nt" else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start mitmdump: {str(e)}")
        
    # 4. Set phone proxy via ADB for all connected devices (with retry loop)
    server_ip = _get_local_ip()
    devices = []
    
    # Retry detection loop
    for attempt in range(5):
        devices = _get_adb_devices(adb_path)
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

@router.post("/adb/proxy/stop")
def api_stop_proxy():
    # 1. Kill mitmdump
    try:
        if os.name == "nt":
            subprocess.run("taskkill /F /IM mitmdump.exe", shell=True, capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "mitmdump"], capture_output=True)
    except Exception:
        pass
        
    # 2. Reset phone proxy on all connected devices
    adb_path = "adb" if os.name != "nt" else os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    devices = _get_adb_devices(adb_path)
    
    for device in devices:
        try:
            subprocess.run(f'"{adb_path}" -s {device} shell settings put global http_proxy :0', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(f'"{adb_path}" -s {device} shell settings delete global http_proxy', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(f'"{adb_path}" -s {device} shell settings delete global global_http_proxy_host', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(f'"{adb_path}" -s {device} shell settings delete global global_http_proxy_port', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        
    return {"status": "stopped", "message": "Proxy stopped and emulator proxy settings cleared."}

@router.get("/adb/proxy/status")
def api_proxy_status():
    # Check if mitmdump process is running (via ps/pgrep on Linux)
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
            
    # Also check if phone proxy is routed on the first connected device
    phone_proxy = "Unknown"
    try:
        adb_path = "adb" if os.name != "nt" else os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
        devices = _get_adb_devices(adb_path)
        if devices:
            device = devices[0]
            val = subprocess.check_output(f'"{adb_path}" -s {device} shell settings get global http_proxy', shell=True, text=True).strip()
            phone_proxy = val if val and val != "null" and val != ":0" else "None"
        else:
            phone_proxy = "Disconnected"
    except Exception:
        phone_proxy = "Disconnected"
        
    return {"running": is_running, "phone_proxy": phone_proxy}

@router.get("/compiled-jsons")
def list_compiled_jsons():
    compiled_folder = os.path.join(os.path.dirname(__file__), "..", "..", "data", "compiled_jsons")
    os.makedirs(compiled_folder, exist_ok=True)
    
    files = []
    for filename in os.listdir(compiled_folder):
        if filename.endswith(".json"):
            path = os.path.join(compiled_folder, filename)
            stat = os.stat(path)
            files.append({
                "filename": filename,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime
            })
            
    # Sort by modified time descending
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files

@router.get("/compiled-jsons/{filename}")
def download_compiled_json(filename: str):
    compiled_folder = os.path.join(os.path.dirname(__file__), "..", "..", "data", "compiled_jsons")
    path = os.path.abspath(os.path.join(compiled_folder, filename))
    # Security check: prevent directory traversal
    if not path.startswith(os.path.abspath(compiled_folder)):
        raise HTTPException(status_code=400, detail="Invalid file path.")
        
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found.")
        
    from fastapi.responses import FileResponse
    return FileResponse(path, filename=filename, media_type="application/json")

@router.delete("/compiled-jsons/{filename}")
def delete_compiled_json(filename: str):
    compiled_folder = os.path.join(os.path.dirname(__file__), "..", "..", "data", "compiled_jsons")
    path = os.path.abspath(os.path.join(compiled_folder, filename))
    if not path.startswith(os.path.abspath(compiled_folder)):
        raise HTTPException(status_code=400, detail="Invalid file path.")
        
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found.")
        
    try:
        os.remove(path)
        return {"status": "deleted", "message": f"Deleted {filename} successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))