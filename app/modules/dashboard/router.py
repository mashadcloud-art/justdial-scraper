import os
import sys
import subprocess
import datetime
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from app.database import get_db, SessionLocal, is_postgres
from app import models
from config import settings

from . import service

router = APIRouter()


def _get_current_user(authorization: str = Header(None)) -> Optional[dict]:
    return service.get_current_user(authorization)


# ==========================================
# DATABASE / SYSTEM STATUS
# ==========================================
@router.get("/api/v1/db-status")
def get_db_status(db: Session = Depends(get_db)):
    from sqlalchemy import text
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


@router.post("/api/v1/db-config")
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


@router.post("/api/v1/system/restart")
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


@router.post("/api/v1/system/update")
def system_update():
    try:
        result = subprocess.run(["git", "pull"], capture_output=True, text=True, check=True)
        return {
            "status": "success",
            "message": "Git pull completed successfully.",
            "output": result.stdout
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update: {str(e)}")


# ==========================================
# BACKGROUND IMAGE DAEMON
# ==========================================
@router.get("/api/v1/daemon/status")
def get_daemon_status():
    is_running = service.is_background_daemon_running()

    db = SessionLocal()
    try:
        total_listings = db.query(models.Listing).count()
        pending_count = db.query(models.Listing.id).outerjoin(models.ListingImage).group_by(models.Listing.id).having(func.count(models.ListingImage.id) <= 1).count()
        completed_count = total_listings - pending_count
    except Exception as e:
        total_listings = 0
        pending_count = 0
        completed_count = 0
        print(f"Error querying daemon stats: {e}")
    finally:
        db.close()

    logs = []
    log_files = ["bg_scraper_logs.txt", "cloud_bg_scraper.log"]
    for f_name in log_files:
        if os.path.exists(f_name):
            try:
                with open(f_name, "r", encoding="utf-8", errors="replace") as lf:
                    lines = lf.readlines()
                    logs = [line.strip() for line in lines[-25:]]
                break
            except Exception:
                pass

    return {
        "total_listings": total_listings,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "is_running": is_running,
        "logs": logs
    }


@router.post("/api/v1/daemon/start")
def start_daemon():
    if service.is_background_daemon_running():
        return {"status": "already_running"}

    try:
        python_exe = sys.executable
        log_file_path = "bg_scraper_logs.txt"
        log_file = open(log_file_path, "a", encoding="utf-8")
        subprocess.Popen(
            [python_exe, "-u", "app/scraper/scrape_background_images.py", "--no-shutdown"],
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
        return {"status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start daemon: {e}")


@router.post("/api/v1/daemon/stop")
def stop_daemon():
    import psutil
    stopped = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            if any('scrape_background_images.py' in part for part in cmd):
                proc.terminate()
                stopped = True
        except Exception:
            pass
    return {"status": "stopped" if stopped else "not_running"}


# ==========================================
# IMAGE PROXY (display listing images pulled from Google)
# ==========================================
@router.get("/api/v1/proxy-image")
async def proxy_image(url: str):
    import httpx
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    if not any(domain in url for domain in ["googleusercontent.com", "google.com", "gstatic.com"]):
        raise HTTPException(status_code=400, detail="Only Google domains are allowed for proxying")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        client = httpx.AsyncClient()

        async def image_stream():
            try:
                async with client.stream("GET", url, headers=headers, timeout=10.0) as r:
                    if r.status_code != 200:
                        yield b""
                        return
                    async for chunk in r.aiter_bytes():
                        yield chunk
            finally:
                await client.aclose()

        content_type = "image/jpeg"
        if ".png" in url.lower():
            content_type = "image/png"
        elif ".webp" in url.lower():
            content_type = "image/webp"
        return StreamingResponse(
            image_stream(),
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to proxy image: {str(e)}")


# ==========================================
# LISTINGS
# ==========================================
@router.get("/api/v1/listings")
@router.get("/api/v1/restaurants", deprecated=True)
def get_listings(
    page: int = 1,
    limit: int = 1000000,
    district: Optional[str] = None,
    state: Optional[str] = None,
    category: Optional[str] = None,
    normalized_category: Optional[str] = None,
    search: Optional[str] = None,
    source: Optional[str] = None,
    sort: Optional[str] = None,
    today_only: Optional[bool] = False,
    db: Session = Depends(get_db),
    current_user: Optional[dict] = Depends(_get_current_user)
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

    query = db.query(models.Listing)
    if current_user:
        query = query.filter(models.Listing.user_id == current_user["user_id"])

    if today_only:
        today_start = datetime.datetime.combine(datetime.datetime.utcnow().date(), datetime.time.min)
        query = query.filter(models.Listing.scraped_at >= today_start)

    if state:
        query = query.filter(models.Listing.state.ilike(f"%{state}%"))
    if district:
        query = query.filter(models.Listing.district.ilike(f"%{district}%"))
    if normalized_category:
        query = query.filter(models.Listing.normalized_category.ilike(f"%{normalized_category}%"))
    if category:
        query = query.filter(
            models.Listing.category.ilike(f"%{category}%") |
            models.Listing.subcategory.ilike(f"%{category}%")
        )
    if source:
        if source.lower() == "google":
            query = query.filter(models.Listing.jd_url.ilike("%google.com/maps%"))
        elif source.lower() == "justdial":
            query = query.filter(models.Listing.jd_url.ilike("%justdial.com%"))
    if search:
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

    query = query.options(
        selectinload(models.Listing.images),
        selectinload(models.Listing.menu_items),
        selectinload(models.Listing.amenities),
        selectinload(models.Listing.professionals)
    )

    if sort == "newest_images":
        listings = query.join(models.ListingImage).group_by(models.Listing.id).order_by(func.max(models.ListingImage.id).desc()).offset((page - 1) * limit).limit(limit).all()
    else:
        listings = query.order_by(models.Listing.id.desc()).offset((page - 1) * limit).limit(limit).all()

    result = []
    for r in listings:
        valid_images = [img for img in r.images if img.image_path and img.image_path not in ["NO_IMAGES_FOUND_FLAG", "CRASH_FLAG"]]
        primary_img = next((img.image_path for img in valid_images if img.is_primary), None)
        if not primary_img and valid_images: primary_img = valid_images[0].image_path

        menu_list = [{"name": m.name, "price": m.price, "is_veg": m.is_veg} for m in r.menu_items]
        amenities_list = [{"category": a.category, "value": a.value} for a in r.amenities]
        images_list = [{"path": img.image_path, "category": img.category or "general"} for img in valid_images]
        professionals_list = [{"name": p.name, "achievement": p.achievement, "tags": p.tags, "image_url": p.image_url} for p in r.professionals]

        result.append({
            "id": getattr(r, "id", None), "name": getattr(r, "name", ""), "phone": getattr(r, "phone", ""), "whatsapp": getattr(r, "whatsapp", ""), "address": getattr(r, "address", ""),
            "jd_url": getattr(r, "jd_url", ""), "category": getattr(r, "category", ""), "subcategory": getattr(r, "subcategory", ""),
            "normalized_category": getattr(r, "normalized_category", ""), "opening_hours": getattr(r, "opening_hours", ""),
            "district": getattr(r, "district", ""), "state": getattr(r, "state", ""), "place": getattr(r, "place", ""),
            "latitude": getattr(r, "latitude", ""), "longitude": getattr(r, "longitude", ""),
            "image_path": primary_img, "menu_items": menu_list, "amenities": amenities_list, "images": images_list,
            "professionals": professionals_list
        })

    result = pros_result + result
    total_count = len(result)

    return {
        "data": result,
        "total_count": total_count,
        "page": page,
        "limit": limit
    }


# ==========================================
# STATS (For the Dashboard)
# ==========================================
@router.get("/api/v1/stats")
def get_stats(db: Session = Depends(get_db), current_user: Optional[dict] = Depends(_get_current_user)):
    user_id = current_user["user_id"] if current_user else None

    total_listings_query = db.query(models.Listing)
    if user_id:
        total_listings_query = total_listings_query.filter(models.Listing.user_id == user_id)
    total_listings = total_listings_query.count()

    if user_id:
        total_images = db.query(models.ListingImage).join(models.Listing).filter(models.Listing.user_id == user_id).count()
        total_menu_items = db.query(models.MenuItem).join(models.Listing).filter(models.Listing.user_id == user_id).count()
    else:
        total_images = db.query(models.ListingImage).count()
        total_menu_items = db.query(models.MenuItem).count()

    today_start = datetime.datetime.combine(datetime.datetime.utcnow().date(), datetime.time.min)
    scraped_today_query = db.query(models.Listing).filter(models.Listing.scraped_at >= today_start)
    if user_id:
        scraped_today_query = scraped_today_query.filter(models.Listing.user_id == user_id)
    scraped_today = scraped_today_query.count()

    cat_counts_query = db.query(
        models.Listing.normalized_category, func.count(models.Listing.id)
    )
    if user_id:
        cat_counts_query = cat_counts_query.filter(models.Listing.user_id == user_id)
    cat_counts = cat_counts_query.group_by(models.Listing.normalized_category).all()
    category_breakdown = {(cat or "Other"): count for cat, count in cat_counts}

    return {
        "total_listings": total_listings,
        "total_businesses": total_listings,
        "total_restaurants": total_listings,  # Backward compatibility
        "total_images": total_images,
        "total_menu_items": total_menu_items,
        "scraped_today": scraped_today,
        "category_breakdown": category_breakdown
    }


@router.get("/api/v1/stats/scraped-today-breakdown")
def get_scraped_today_breakdown(db: Session = Depends(get_db), current_user: Optional[dict] = Depends(_get_current_user)):
    today_start = datetime.datetime.combine(datetime.datetime.utcnow().date(), datetime.time.min)
    user_id = current_user["user_id"] if current_user else None

    city_counts_query = db.query(
        models.Listing.district, func.count(models.Listing.id)
    ).filter(models.Listing.scraped_at >= today_start)
    if user_id:
        city_counts_query = city_counts_query.filter(models.Listing.user_id == user_id)
    city_counts = city_counts_query.group_by(models.Listing.district).order_by(func.count(models.Listing.id).desc()).all()

    cat_counts_query = db.query(
        models.Listing.category, func.count(models.Listing.id)
    ).filter(models.Listing.scraped_at >= today_start)
    if user_id:
        cat_counts_query = cat_counts_query.filter(models.Listing.user_id == user_id)
    cat_counts = cat_counts_query.group_by(models.Listing.category).order_by(func.count(models.Listing.id).desc()).all()

    combo_counts_query = db.query(
        models.Listing.district, models.Listing.category, func.count(models.Listing.id)
    ).filter(models.Listing.scraped_at >= today_start)
    if user_id:
        combo_counts_query = combo_counts_query.filter(models.Listing.user_id == user_id)
    combo_counts = combo_counts_query.group_by(models.Listing.district, models.Listing.category).order_by(func.count(models.Listing.id).desc()).all()

    return {
        "by_city": [{"city": (city or "Unknown"), "count": count} for city, count in city_counts],
        "by_category": [{"category": (cat or "Unknown"), "count": count} for cat, count in cat_counts],
        "by_combo": [{"city": (city or "Unknown"), "category": (cat or "Unknown"), "count": count} for city, cat, count in combo_counts]
    }


# ==========================================
# COVERAGE TRACKER
# ==========================================
@router.get("/api/v1/coverage")
def get_coverage(db: Session = Depends(get_db), current_user: Optional[dict] = Depends(_get_current_user)):
    user_id = current_user["user_id"] if current_user else None

    coverage_counts_query = db.query(
        models.Listing.state,
        models.Listing.district,
        models.Listing.category,
        func.count(models.Listing.id)
    )
    if user_id:
        coverage_counts_query = coverage_counts_query.filter(models.Listing.user_id == user_id)
    coverage_counts = coverage_counts_query.group_by(
        models.Listing.state,
        models.Listing.district,
        models.Listing.category
    ).all()

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
# CATEGORY SUMMARY — grouped parent categories with raw sub-category breakdown
# ==========================================
@router.get("/api/v1/categories/summary")
def get_categories_summary(db: Session = Depends(get_db)):
    """
    Returns all parent normalized categories with their counts
    and the breakdown of raw JustDial sub-categories within each.
    """
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

    result = dict(sorted(result.items(), key=lambda x: -x[1]["count"]))
    for parent in result:
        result[parent]["raw_categories"] = dict(
            sorted(result[parent]["raw_categories"].items(), key=lambda x: -x[1])
        )

    return result


# ==========================================
# DELETE DUPLICATES
# ==========================================
@router.post("/api/v1/delete-duplicates")
def delete_duplicates(db: Session = Depends(get_db), current_user: Optional[dict] = Depends(_get_current_user)):
    user_id = current_user["user_id"] if current_user else None
    query = db.query(models.Listing)
    if user_id:
        query = query.filter(models.Listing.user_id == user_id)
    listings = query.all()
    seen = {}
    duplicates = []

    for r in listings:
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
# DELETE SINGLE LISTING
# ==========================================
@router.delete("/api/v1/listing/{listing_id}")
@router.delete("/api/v1/restaurant/{listing_id}", deprecated=True)
def delete_listing(listing_id: int, delete_images: bool = False, db: Session = Depends(get_db), current_user: Optional[dict] = Depends(_get_current_user)):
    user_id = current_user["user_id"] if current_user else None
    query = db.query(models.Listing).filter(models.Listing.id == listing_id)
    if user_id:
        query = query.filter(models.Listing.user_id == user_id)
    listing = query.first()

    if not listing:
        raise HTTPException(status_code=404, detail=f"Listing with ID {listing_id} not found or access denied")

    image_paths = []
    if delete_images:
        for img in listing.images:
            if img.image_path and os.path.exists(img.image_path):
                image_paths.append(img.image_path)

    db.delete(listing)
    db.commit()

    if delete_images and image_paths:
        def delete_files():
            for img_path in image_paths:
                try:
                    os.remove(img_path)
                except Exception:
                    pass
        threading.Thread(target=delete_files).start()

    return {"status": "success", "deleted_id": listing_id}


# ==========================================
# CLEAR ALL DATA (Danger Zone)
# ==========================================
@router.post("/api/v1/clear-all")
def clear_all(db: Session = Depends(get_db), current_user: Optional[dict] = Depends(_get_current_user)):
    user_id = current_user["user_id"] if current_user else None

    if user_id:
        user_listing_ids = [r[0] for r in db.query(models.Listing.id).filter(models.Listing.user_id == user_id).all()]
        if user_listing_ids:
            images = db.query(models.ListingImage).filter(models.ListingImage.listing_id.in_(user_listing_ids)).all()
            image_paths = [img.image_path for img in images if img.image_path and os.path.exists(img.image_path)]

            db.query(models.MenuItem).filter(models.MenuItem.listing_id.in_(user_listing_ids)).delete(synchronize_session=False)
            db.query(models.Amenity).filter(models.Amenity.listing_id.in_(user_listing_ids)).delete(synchronize_session=False)
            db.query(models.ListingImage).filter(models.ListingImage.listing_id.in_(user_listing_ids)).delete(synchronize_session=False)
            db.query(models.Listing).filter(models.Listing.id.in_(user_listing_ids)).delete(synchronize_session=False)
            db.commit()
        else:
            image_paths = []
    else:
        images = db.query(models.ListingImage).all()
        image_paths = [img.image_path for img in images if img.image_path and os.path.exists(img.image_path)]

        db.query(models.MenuItem).delete()
        db.query(models.Amenity).delete()
        db.query(models.ListingImage).delete()
        db.query(models.Listing).delete()
        db.commit()

    if image_paths:
        def delete_all_files():
            for img_path in image_paths:
                try:
                    os.remove(img_path)
                except Exception:
                    pass
        threading.Thread(target=delete_all_files).start()

    return {"status": "success"}
