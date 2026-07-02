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
from app.scraper.emulator_parser import (
    get_state_from_district,
    extract_place_from_address,
    detect_category_from_name,
    extract_district_from_address,
    reverse_geocode_coords
)
from app.scraper.category_normalizer import normalize_category

# Cuisine keywords to split category/subcategory
CUISINE_KEYWORDS = [
    "South Indian", "North Indian", "Punjabi", "Chinese", "Continental",
    "Mughlai", "Bengali", "Gujarati", "Rajasthani", "Kerala", "Udupi",
    "Multicuisine", "Fast Food", "Barbeque", "Buffet", "Sea Food", "Seafood",
    "Veg", "Non Veg", "Street Food", "Desserts", "Italian", "Thai", "Mexican",
    "Pure Veg", "Tandoor", "Biryani", "Barbecue", "Pizza", "Bakery",
    "Ice Cream", "Juice", "Cafe", "Coffee", "Tea Stall", "Dhaba",
    "Bar", "Lounge", "Fine Dining", "Family Restaurant", "Vegetarian",
]

def looks_like_cuisine_tags(category: str) -> bool:
    if not category:
        return False
    cat_lower = category.lower()
    return any(kw.lower() in cat_lower for kw in CUISINE_KEYWORDS)

def process_category_subcategory(raw_category: str):
    if not raw_category:
        return "Restaurants", None
    
    if ">" in raw_category:
        parts = raw_category.split(">", 1)
        return parts[0].strip(), parts[1].strip()
        
    if looks_like_cuisine_tags(raw_category):
        return "Restaurants", raw_category
        
    return raw_category, None

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

@router.get("/db-status")
def get_db_status(db: Session = Depends(get_db)):
    from sqlalchemy import text
    from app.database import is_postgres
    try:
        db.execute(text("SELECT 1"))
        db_type = "PostgreSQL (Supabase)" if is_postgres else "SQLite (Local)"
        db_url = settings.DATABASE_URL
        if "@" in db_url:
            db_url = db_url.split("@")[-1]
        return {
            "connected": True,
            "type": db_type,
            "url": db_url
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }

@router.post("/db-config")
def update_db_config(payload: dict):
    from app_config import CONFIG_FILE, save_config
    import yaml
    try:
        current_config = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                current_config = yaml.safe_load(f) or {}
        
        if "db_url" in payload:
            if "database" not in current_config:
                current_config["database"] = {}
            current_config["database"]["url"] = payload["db_url"]
            
        if "supabase_url" in payload:
            if "supabase" not in current_config:
                current_config["supabase"] = {}
            current_config["supabase"]["url"] = payload["supabase_url"]
            
        if "supabase_anon_key" in payload:
            if "supabase" not in current_config:
                current_config["supabase"] = {}
            current_config["supabase"]["anon_key"] = payload["supabase_anon_key"]
            
        save_config(current_config)
        return {"status": "success", "message": "Configuration updated! Please restart the backend to apply changes."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/system/restart")
def restart_server(background_tasks: BackgroundTasks):
    import time
    def do_restart():
        time.sleep(1)
        script_path = os.path.join(os.getcwd(), "Restart_App.bat")
        if os.path.exists(script_path):
            subprocess.Popen(["cmd.exe", "/c", "start", script_path], shell=True)
            os._exit(0)
    
    background_tasks.add_task(do_restart)
    return {"status": "success", "message": "Restarting server..."}


def _get_adb_path():
    if os.name == "nt":
        bluestacks_adb = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
        if os.path.exists(bluestacks_adb):
            return bluestacks_adb
        scrcpy_adb = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scratch", "scrcpy", "scrcpy-win64-v4.0", "adb.exe"))
        if os.path.exists(scrcpy_adb):
            return scrcpy_adb
        return os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    return "adb"


def _get_adb_devices(adb_path):
    try:
        if os.name != "nt":
            # On remote Linux server, connect to desktop emulator over Tailscale VPN
            try:
                subprocess.run(f'"{adb_path}" connect 100.103.62.50:5555', shell=True, timeout=8)
            except Exception:
                pass
        else:
            # On Windows local machine, connect to local BlueStacks instance
            # ONLY connect if we are NOT using the BlueStacks HD-Adb.exe
            if "HD-Adb.exe" not in adb_path:
                try:
                    subprocess.run(f'"{adb_path}" connect 127.0.0.1:5555', shell=True, timeout=5)
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

# ==========================================
# ADB DEVICE MANAGER
# ==========================================
from pydantic import BaseModel
class DeviceSelection(BaseModel):
    device_id: str

@router.get("/adb/devices")
def get_all_adb_devices():
    adb_path = _get_adb_path()
    # Try to connect standard emulator ports just in case
    if os.name == "nt" and "HD-Adb.exe" not in adb_path:
        for port in [5555, 5556, 5557, 5558, 5585, 5554]:
            try: subprocess.run(f'"{adb_path}" connect 127.0.0.1:{port}', shell=True, timeout=2)
            except: pass
            
    devices = _get_adb_devices(adb_path)
    
    result = []
    for d in devices:
        # Try to get device model for better UI
        model = d
        try:
            out = subprocess.check_output(f'"{adb_path}" -s {d} shell getprop ro.product.model', shell=True, text=True, timeout=2)
            if out.strip(): model = f"{out.strip()} ({d})"
        except: pass
        result.append({"id": d, "name": model})
    return {"devices": result}

@router.post("/adb/device/select")
def select_adb_device(selection: DeviceSelection):
    config_path = os.path.join(settings.DATA_FOLDER, "active_device.txt")
    with open(config_path, "w") as f:
        f.write(selection.device_id.strip())
    return {"status": "success", "device_id": selection.device_id}

@router.get("/adb/device/active")
def get_active_adb_device():
    config_path = os.path.join(settings.DATA_FOLDER, "active_device.txt")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            device = f.read().strip()
            if device:
                return {"device_id": device}
    return {"device_id": None}

# ==========================================
# 1. UPLOAD LISTING (Existing)
# ==========================================
import threading
ingest_lock = threading.Lock()

@router.post("/upload-listing", status_code=201)
@router.post("/upload-restaurant", status_code=201, deprecated=True)
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
    db: Session = Depends(get_db)
):
    try:
        # Hybrid Location Engine: Try Coordinate Reverse Geocoding first, fallback to address text parsing
        geo_info = reverse_geocode_coords(latitude, longitude)
        if geo_info:
            if geo_info.get("district"):
                district = geo_info["district"]
            cleaned_state = geo_info.get("state") or state or get_state_from_district(district or "")
            
            # Construct place value
            town_val = geo_info.get("town") or ""
            local_val = geo_info.get("local_area") or ""
            if local_val and town_val and local_val.lower() != town_val.lower():
                cleaned_place = f"{local_val}, {town_val}"
            else:
                cleaned_place = local_val or town_val
        else:
            # Overwrite district with one found in address if any
            addr_district = extract_district_from_address(address or "")
            if addr_district:
                district = addr_district
                
            cleaned_state = state or get_state_from_district(district or "")
            cleaned_place = extract_place_from_address(address or "", district or "")

        # Segregate category & subcategory, assign state and place
        cleaned_cat = category or ""
        cleaned_sub = None
        
        if cleaned_cat:
            cleaned_cat, cleaned_sub = process_category_subcategory(cleaned_cat)
        
        # Detect if business name contains building/complex keywords
        cleaned_cat = detect_category_from_name(name, cleaned_cat)
        
        # Auto-tag normalized parent category (e.g., "Beauty & Spas", "Hotels & Restaurants")
        normalized_cat = normalize_category(cleaned_cat)
        
        # ── AUTO LOCATION CORRECTION ──
        if latitude and longitude:
            try:
                # Do reverse geocoding to fix incorrect JustDial locations (Pincode, District, City)
                correction = get_corrected_location(latitude, longitude, current_district=district, current_place=cleaned_place)
                if correction.get("corrected"):
                    # Apply corrections
                    if correction.get("correct_district"):
                        district = correction["correct_district"]
                    if correction.get("correct_city"):
                        cleaned_place = correction["correct_city"]
                    if correction.get("correct_state"):
                        cleaned_state = correction["correct_state"]
                    # Optionally log: print(f"Corrected Location for {name}: {correction['notes']}")
            except Exception as e:
                print(f"Location correction failed for {name}: {e}")

        with ingest_lock:
            existing = db.query(models.Listing).filter(models.Listing.name == name).first()
            
            if existing:
                listing = existing
                # Only overwrite fields if new value is provided (never blank out existing data)
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
                # Only clear menus/amenities to re-enrich — NOT images (keep mobile API images)
                listing.menu_items.clear()
                listing.amenities.clear()
                # Only clear images if new ones are being uploaded (don't wipe mobile API images)
                if images or image_urls_json:
                    listing.images.clear()
            else:
                listing = models.Listing(
                    name=name, phone=phone or "", whatsapp=whatsapp or "", address=address or "",
                    jd_url=source_url, category=cleaned_cat or "", subcategory=cleaned_sub, normalized_category=normalized_cat or "Other",
                    opening_hours=opening_hours or "",
                    district=district or "", place=cleaned_place or "", state=cleaned_state or "", latitude=latitude or "", longitude=longitude or ""
                )
                db.add(listing)
                db.flush()
                
            listing_id = listing.id

        # Add menu items (robustly)
        if menu_json:
            try:
                for item in json.loads(menu_json):
                    db.add(models.MenuItem(listing_id=listing_id, name=str(item.get('name', '')), price=str(item.get('price', '0')), is_veg=bool(item.get('is_veg', True))))
            except Exception as menu_e:
                pass  # Ignore menu errors, still save other data

        # Add amenities robustly
        if amenities_json:
            try:
                amenities_data = json.loads(amenities_json)
                if isinstance(amenities_data, dict):
                    for category, values in amenities_data.items():
                        if isinstance(values, list):
                                # Truncate category to 100 characters and value to 200 characters to respect database column limits
                                db.add(models.Amenity(
                                    listing_id=listing_id, 
                                    category=str(category)[:100], 
                                    value=str(val)[:200]
                                ))
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
                        db.add(models.ListingImage(
                            listing_id=listing_id,
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
                        db.add(models.ListingImage(listing_id=listing_id, image_path=image_path, category=cat, is_primary=(i == 0)))
                except Exception as img_e:
                    pass  # Skip image fails, still save rest

        db.commit()
        return {"message": "Success", "listing_id": listing_id}

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
# 2. GET ALL LISTINGS (Existing)
# ==========================================
@router.get("/listings")
@router.get("/restaurants", deprecated=True)
def get_listings(
    page: int = 1, 
    limit: int = 1000000, 
    district: Optional[str] = None, 
    state: Optional[str] = None, 
    category: Optional[str] = None,
    normalized_category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # 1. Search Professionals Union
    pros_result = []
    if search:
        keywords = search.strip().split()
        pro_query = db.query(models.Professional)
        for kw in keywords:
            pro_query = pro_query.filter(
                models.Professional.name.ilike(f"%{kw}%") |
                models.Professional.tags.ilike(f"%{kw}%")
            )
        matching_pros = pro_query.all()
        for p in matching_pros:
            parent_listing = db.query(models.Listing).filter(models.Listing.id == p.listing_id).first()
            district_val = parent_listing.district if parent_listing else ""
            state_val = parent_listing.state if parent_listing else ""
            
            pros_result.append({
                "id": f"pro_{p.id}",
                "name": p.name,
                "phone": "-",
                "whatsapp": None,
                "address": f"Student at: {parent_listing.name if parent_listing else 'SEED Campus'}",
                "jd_url": "",
                "category": p.tags if p.tags else "ACCA Professional",
                "subcategory": "Placed Students",
                "normalized_category": "Education Professionals",
                "opening_hours": "N/A",
                "district": district_val,
                "state": state_val,
                "place": "",
                "latitude": "",
                "longitude": "",
                "image_path": p.image_url,
                "menu_items": [],
                "amenities": [{"category": "Achievement", "value": p.achievement}],
                "images": [{"path": p.image_url, "category": "general"}]
            })

    # Standard Listing Query Fallback
    query = db.query(models.Listing)
    
    if state:
        query = query.filter(models.Listing.state.ilike(f"%{state}%"))
    if district:
        query = query.filter(models.Listing.district.ilike(f"%{district}%"))
    if normalized_category:
        # Search by parent group: e.g., "Beauty & Spas" returns ALL salons, spas, parlours, etc.
        query = query.filter(models.Listing.normalized_category.ilike(f"%{normalized_category}%"))
    if category:
        # Search by specific raw category: e.g., "Salons" returns ONLY salons
        query = query.filter(
            models.Listing.category.ilike(f"%{category}%") |
            models.Listing.subcategory.ilike(f"%{category}%")
        )
    if search:
        # Split search into individual words for smarter matching across different columns
        keywords = search.strip().split()
        for kw in keywords:
            query = query.filter(
                models.Listing.name.ilike(f"%{kw}%") |
                models.Listing.category.ilike(f"%{kw}%") |
                models.Listing.address.ilike(f"%{kw}%") |
                models.Listing.phone.ilike(f"%{kw}%") |
                models.Listing.district.ilike(f"%{kw}%") |
                models.Listing.id.in_(
                    db.query(models.Professional.listing_id).filter(
                        models.Professional.name.ilike(f"%{kw}%") |
                        models.Professional.tags.ilike(f"%{kw}%")
                    )
                )
            )
        
    listings = query.options(
        selectinload(models.Listing.images),
        selectinload(models.Listing.menu_items),
        selectinload(models.Listing.amenities)
    ).order_by(models.Listing.id.desc()).offset((page - 1) * limit).limit(limit).all()
    
    result = []
    for r in listings:
        primary_img = next((img.image_path for img in r.images if img.is_primary), None)
        if not primary_img and r.images: primary_img = r.images[0].image_path
            
        menu_list = [{"name": m.name, "price": m.price, "is_veg": m.is_veg} for m in r.menu_items]
        amenities_list = [{"category": a.category, "value": a.value} for a in r.amenities]
        images_list = [{"path": img.image_path, "category": img.category or "general"} for img in r.images]
        
        result.append({
            "id": getattr(r, "id", None), "name": getattr(r, "name", ""), "phone": getattr(r, "phone", ""), "whatsapp": getattr(r, "whatsapp", ""), "address": getattr(r, "address", ""),
            "jd_url": getattr(r, "jd_url", ""), "category": getattr(r, "category", ""), "subcategory": getattr(r, "subcategory", ""),
            "normalized_category": getattr(r, "normalized_category", ""), "opening_hours": getattr(r, "opening_hours", ""),
            "district": getattr(r, "district", ""), "state": getattr(r, "state", ""), "place": getattr(r, "place", ""),
            "latitude": getattr(r, "latitude", ""), "longitude": getattr(r, "longitude", ""),
            "image_path": primary_img, "menu_items": menu_list, "amenities": amenities_list, "images": images_list
        })
        
    # Append professionals to the results list
    result = pros_result + result
    total_count = len(result)
        
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
    from sqlalchemy import func
    total_listings = db.query(models.Listing).count()
    total_images = db.query(models.ListingImage).count()
    total_menu_items = db.query(models.MenuItem).count()
    
    # Category group counts (schools are now merged into listings table)
    cat_counts = db.query(
        models.Listing.normalized_category, func.count(models.Listing.id)
    ).group_by(models.Listing.normalized_category).all()
    category_breakdown = {(cat or "Other"): count for cat, count in cat_counts}
    
    return {
        "total_listings": total_listings,
        "total_restaurants": total_listings, # Backward compatibility
        "total_images": total_images,
        "total_menu_items": total_menu_items,
        "category_breakdown": category_breakdown
    }

# ==========================================
# 3a. NEW: COVERAGE TRACKER
# ==========================================
@router.get("/coverage")
def get_coverage(db: Session = Depends(get_db)):
    from sqlalchemy import func
    # Group by state, district, category and count
    coverage_counts = db.query(
        models.Listing.state,
        models.Listing.district,
        models.Listing.category,
        func.count(models.Listing.id)
    ).group_by(
        models.Listing.state,
        models.Listing.district,
        models.Listing.category
    ).all()
    
    # Format the data into a structured dictionary
    # { "Kerala": { "Ernakulam": { "Banquet Halls": 1200 } } }
    result = {}
    for state, district, category, count in coverage_counts:
        st = state or "Unknown State"
        dist = district or "Unknown District"
        cat = category or "Unknown Category"
        
        if st not in result:
            result[st] = {}
        if dist not in result[st]:
            result[st][dist] = {}
        result[st][dist][cat] = count
        
    return {"coverage": result}

# ==========================================
# 3b. CATEGORY SUMMARY — grouped parent categories with raw sub-category breakdown
# ==========================================
@router.get("/categories/summary")
def get_categories_summary(db: Session = Depends(get_db)):
    """
    Returns all parent normalized categories with their counts
    and the breakdown of raw JustDial sub-categories within each.
    
    Example response:
    {
      "Beauty & Spas": {
        "count": 750,
        "raw_categories": {"Beauty Parlours": 462, "Salons": 145, "Hair Stylists": 9, ...}
      }
    }
    """
    from sqlalchemy import func
    
    # Get all normalized_category + category combos with counts
    rows = db.query(
        models.Listing.normalized_category,
        models.Listing.category,
        func.count(models.Listing.id)
    ).group_by(
        models.Listing.normalized_category,
        models.Listing.category
    ).all()
    
    result = {}
    for norm_cat, raw_cat, count in rows:
        parent = norm_cat or "Other"
        if parent not in result:
            result[parent] = {"count": 0, "raw_categories": {}}
        result[parent]["count"] += count
        if raw_cat:
            result[parent]["raw_categories"][raw_cat] = count
    
    # Sort by count descending
    result = dict(sorted(result.items(), key=lambda x: -x[1]["count"]))
    # Sort raw_categories within each parent
    for parent in result:
        result[parent]["raw_categories"] = dict(
            sorted(result[parent]["raw_categories"].items(), key=lambda x: -x[1])
        )
    
    return result

# ==========================================
# 4. NEW: DELETE DUPLICATES
# ==========================================
@router.post("/delete-duplicates")
def delete_duplicates(db: Session = Depends(get_db)):
    listings = db.query(models.Listing).all()
    seen = {}
    duplicates = []
    
    for r in listings:
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
# 5. NEW: DELETE SINGLE LISTING
# ==========================================
@router.delete("/listing/{listing_id}")
@router.delete("/restaurant/{listing_id}", deprecated=True)
def delete_listing(listing_id: int, delete_images: bool = False, db: Session = Depends(get_db)):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    
    if not listing:
        raise HTTPException(status_code=404, detail=f"Listing with ID {listing_id} not found")
    
    # Collect images to delete if needed
    image_paths = []
    if delete_images:
        for img in listing.images:
            if img.image_path and os.path.exists(img.image_path):
                image_paths.append(img.image_path)
    
    # Delete from DB (SQLAlchemy handles cascading delete for related items)
    db.delete(listing)
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
    
    return {"status": "success", "deleted_id": listing_id}

# ==========================================
# 6. NEW: CLEAR ALL DATA (Danger Zone)
# ==========================================
@router.post("/clear-all")
def clear_all(db: Session = Depends(get_db)):
    # First collect all image paths
    images = db.query(models.ListingImage).all()
    image_paths = [img.image_path for img in images if img.image_path and os.path.exists(img.image_path)]
    
    # Delete from DB
    db.query(models.MenuItem).delete()
    db.query(models.Amenity).delete()
    db.query(models.ListingImage).delete()
    db.query(models.Listing).delete()
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
adb_search_in_progress = False

def _clear_stop_flag():
    flag_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "scrape_stop.flag")
    if os.path.exists(flag_path):
        try:
            os.remove(flag_path)
        except:
            pass

@router.post("/scrape/stop")
def stop_scrape():
    global scraping_in_progress, scraping_started_at, adb_search_in_progress
    scraping_in_progress = False
    scraping_started_at = None
    adb_search_in_progress = False
    
    flag_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "scrape_stop.flag")
    os.makedirs(os.path.dirname(flag_path), exist_ok=True)
    with open(flag_path, "w") as f:
        f.write("stop")
    log("🛑 Scraper stop requested by user (stop flag created).")
    return {"status": "stopped", "message": "Scraper stop signal sent."}

@router.post("/scrape/reset")
def reset_scrape_lock():
    """Force-reset the scrape lock if a task got stuck"""
    global scraping_in_progress, scraping_started_at, adb_search_in_progress
    was_locked = scraping_in_progress
    scraping_in_progress = False
    scraping_started_at = None
    adb_search_in_progress = False
    _clear_stop_flag()
    return {"status": "reset", "was_locked": was_locked, "message": "Scrape lock cleared."}

@router.post("/scrape/clear-history")
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
    _clear_stop_flag()
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
            
            # Load progress history
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
                        from app.scraper.adb_location_search import automate_location_search
                        from app.scraper.constants import get_areas_for_district
                        search_cat = subcat if (subcat and subcat not in ["All", "—"]) else main_cat
                        # Auto-generate all major areas for the district
                        areas = get_areas_for_district(city)
                        log(f"ADB Emulator: '{search_cat}' in '{city}' — {len(areas)} areas to search: {', '.join(areas)}")
                        automate_location_search(areas, search_cat, scrolls=max_limit, city=city)
                    elif engine == "jwt_api":
                        from jd_api_scraper import scrape_jwt_city
                        search_cat = subcat if (subcat and subcat not in ["All", "—"]) else main_cat
                        scrape_jwt_city(city, search_cat, pages=max_limit, limit=100, dry_run=False)
                    else:
                        selenium_scrape_city(city, main_cat, subcat, max_limit=max_limit, fast_mode=fast_mode, start_page=start_page, browser_type="chrome")
                    
                    # Mark as completed and save to history
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

@router.post("/scrape/cli")
async def trigger_cli_scrape(request: Request, background_tasks: BackgroundTasks):
    global scraping_in_progress, scraping_started_at
    _clear_stop_flag()
    if scraping_in_progress:
        raise HTTPException(status_code=400, detail="Scrape task is already in progress.")
        
    data = await request.json()
    cmd_str = data.get("command", "").strip()
    
    if not cmd_str.startswith("python jd_api_scraper.py") and not cmd_str.startswith("python3 jd_api_scraper.py") and not cmd_str.startswith("python scrape_"):
        raise HTTPException(status_code=400, detail="Only jd_api_scraper.py or scrape_*.py commands are allowed for safety.")
        
    scraper_logger.clear()
    
    def run_cli_scrape():
        global scraping_in_progress, scraping_started_at
        import time as _time
        import shlex
        scraping_started_at = _time.time()
        scraping_in_progress = True
        
        log(f"💻 Starting CLI Scrape: {cmd_str}")
        def _is_stop_requested():
            flag_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "scrape_stop.flag")
            return os.path.exists(flag_path)

        try:
            process = subprocess.Popen(
                shlex.split(cmd_str),
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
            scraping_in_progress = False
            scraping_started_at = None

    background_tasks.add_task(run_cli_scrape)
    return {"status": "started", "message": "CLI command started."}

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
    _clear_stop_flag()
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
async def ingest_emulator_json(request: Request, district: str = "Unknown", main_cat: str = ""):
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
        success_count = process_emulator_json(json_data, district, main_cat=main_cat)
        
        return {"status": "success", "message": f"Successfully ingested {success_count} listings.", "count": success_count}
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

@router.post("/ingest-uploaded-file")
async def ingest_uploaded_file(
    file: UploadFile = File(...),
    district: str = Form("Unknown"),
    category: str = Form("Unknown")
):
    """
    Accepts an uploaded JSON file, parses it, and inserts it into the database under a specific category and district.
    """
    try:
        from app.scraper.emulator_parser import process_emulator_json
        import json
        
        contents = await file.read()
        try:
            data = json.loads(contents.decode("utf-8"))
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid JSON file format.")

        # In case the JSON payload contains "json_data" key, process it, otherwise wrap it
        if isinstance(data, dict) and "json_data" not in data:
            # Wrap standard raw JSON so emulator_parser can process it
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
# 9. TRIGGER ADB LOCATION SEARCH (Emulator Bridge)
# ==========================================
from app.scraper.adb_location_search import automate_location_search

@router.post("/adb/search")
def trigger_adb_search(
    location: str,
    category: str = "Restaurants",
    scrolls: int = 15,
    background_tasks: BackgroundTasks = None
):
    global adb_search_in_progress
    _clear_stop_flag()
    if adb_search_in_progress:
        raise HTTPException(status_code=400, detail="ADB search is already in progress on the emulator.")
        
    # Clear logs so the user sees fresh logs for their emulator run
    scraper_logger.clear()
        
    def run_adb_search():
        global adb_search_in_progress
        try:
            adb_search_in_progress = True
            from app.scraper.constants import get_areas_for_district
            areas = get_areas_for_district(location)
            log(f"ADB Bridge: '{category}' in '{location}' — {len(areas)} areas: {', '.join(areas)}")
            automate_location_search(areas, category, scrolls, city=location)
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
    
    adb_path = _get_adb_path()
    devices = _get_adb_devices(adb_path)
    target = ""
    
    # Check active_device.txt
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
    import os, json
    _clear_stop_flag()
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
                from app.scraper.adb_location_search import check_stop_flag
                if check_stop_flag():
                    log("🛑 SMART SCRAPE: Stopped by user request. Exiting outer loop.")
                    break
                log(f"SMART SCRAPE: Processing subcategory -> {sub}")
                automate_location_search(pincodes, sub, scrolls, city=district)
                
            from app.scraper.adb_location_search import check_stop_flag
            if check_stop_flag():
                log("🛑 SMART SCRAPE: Exited early due to user stop request.")
            else:
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
    if os.name != "nt":
        try:
            # Try to get tailscale0 IP address
            import subprocess
            out = subprocess.check_output("ip -o -4 addr show dev tailscale0", shell=True, text=True)
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    ip = parts[3].split('/')[0]
                    if ip.startswith("100."):
                        return ip
        except Exception:
            pass
        return "129.151.146.44"
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

# _get_adb_devices is defined at the top of the file

@router.post("/adb/proxy/start")
def api_start_proxy():
    import time
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
    adb_path = _get_adb_path()
    
    # Dynamically locate mitmdump path based on environment
    import sys
    import shutil
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
    adb_path = _get_adb_path()
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
        adb_path = _get_adb_path()
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

_scroll_process = None

@router.post("/adb/scroll/start")
def api_start_scroll(interval: float = 3.0):
    global _scroll_process
    if _scroll_process and _scroll_process.poll() is None:
        return {"status": "already_running", "message": "Auto-scroll is already running."}
    
    try:
        import sys
        _scroll_process = subprocess.Popen(
            [sys.executable, "-u", "-m", "app.scraper.adb_controller", "--interval", str(interval)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.join(os.path.dirname(__file__), "..", "..")
        )
        return {"status": "started", "message": "Auto-scroll started successfully."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to start auto-scroll: {e}"}

@router.post("/adb/scroll/stop")
def api_stop_scroll():
    global _scroll_process
    if _scroll_process and _scroll_process.poll() is None:
        _scroll_process.terminate()
        _scroll_process = None
        return {"status": "stopped", "message": "Auto-scroll stopped successfully."}
    return {"status": "not_running", "message": "Auto-scroll is not running."}

@router.get("/adb/scroll/status")
def api_scroll_status():
    global _scroll_process
    is_running = _scroll_process is not None and _scroll_process.poll() is None
    return {"running": is_running}

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

@router.post("/compiled-jsons/{filename}/ingest")
def ingest_compiled_json(filename: str):
    compiled_folder = os.path.join(os.path.dirname(__file__), "..", "..", "data", "compiled_jsons")
    path = os.path.abspath(os.path.join(compiled_folder, filename))
    if not path.startswith(os.path.abspath(compiled_folder)):
        raise HTTPException(status_code=400, detail="Invalid file path.")
        
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found.")
        
    try:
        from app.scraper.emulator_parser import process_emulator_json
        import json
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Try to infer district from filename (e.g. Thiruvananthapuram_Fast Food_Compiled.json)
        district = "Unknown"
        if "_" in filename:
            district = filename.split("_")[0]
            
        count = process_emulator_json(data, district)
        return {"status": "success", "message": f"Successfully ingested {count} listings from {filename}.", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest: {str(e)}")

@router.post("/adb/scrcpy/start")
def start_scrcpy_mirror():
    import subprocess
    import os
    
    adb_path = _get_adb_path()
    # Resolve scrcpy.exe path relative to adb_path
    if "scrcpy-win64" in adb_path:
        scrcpy_exe = adb_path.replace("adb.exe", "scrcpy.exe")
    else:
        scrcpy_exe = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scratch", "scrcpy", "scrcpy-win64-v4.0", "scrcpy.exe"))
        
    if not os.path.exists(scrcpy_exe):
        raise HTTPException(status_code=404, detail="scrcpy.exe not found.")
        
    devices = _get_adb_devices(adb_path)
    target_device = ""
    
    # Read active device
    config_path = os.path.join(settings.DATA_FOLDER, "active_device.txt")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            saved_device = f.read().strip()
            if saved_device and saved_device in devices:
                target_device = saved_device
                
    if not target_device and devices:
        target_device = devices[0]
        
    if not target_device:
        # Fallback to the default Tailscale IP
        target_device = "100.110.105.12:5555"
        # Try to connect it first
        try:
            subprocess.run(f'"{adb_path}" connect {target_device}', shell=True, timeout=5)
        except Exception:
            pass

    try:
        # Launch scrcpy in the background as a separate process without locking FastAPI
        cmd = f'"{scrcpy_exe}" -s {target_device} --tcpip={target_device}'
        subprocess.Popen(cmd, shell=True)
        return {"status": "success", "message": f"scrcpy started for {target_device}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/phone/screen")
def get_phone_screen_api():
    import io
    from fastapi.responses import StreamingResponse
    
    adb_path = _get_adb_path()
    devices = _get_adb_devices(adb_path)
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
        target = "-s 100.110.105.12:5555" # Default fallback
        
    cmd = f'"{adb_path}" {target} shell screencap -p'
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode == 0:
        return StreamingResponse(io.BytesIO(result.stdout), media_type="image/png")
    return {"error": "Failed to capture screen or device offline"}

@router.get("/phone/control")
def control_phone_api(action: str, x: int = None, y: int = None):
    adb_path = _get_adb_path()
    devices = _get_adb_devices(adb_path)
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
        target = "-s 100.110.105.12:5555" # Default fallback
        
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

@router.get("/phone/size")
def get_phone_size_api():
    adb_path = _get_adb_path()
    devices = _get_adb_devices(adb_path)
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
        target = "-s 100.110.105.12:5555" # Default fallback
        
    try:
        out = subprocess.check_output(f'"{adb_path}" {target} shell wm size', shell=True, text=True, timeout=3)
        if "size:" in out:
            size_str = out.split("size:")[-1].strip()
            w, h = map(int, size_str.split("x"))
            return {"width": w, "height": h}
    except Exception:
        pass
    return {"width": 1440, "height": 2960}