import sys
import os
import shutil
import datetime
import json
import traceback
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
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
    menu_json: Optional[str] = Form(None),
    amenities_json: Optional[str] = Form(None),
    image_categories: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)
):
    try:
        existing = db.query(models.Restaurant).filter(models.Restaurant.name == name).first()
        
        if existing:
            restaurant = existing
            restaurant.phone = phone or existing.phone
            restaurant.whatsapp = whatsapp or existing.whatsapp
            restaurant.address = address or existing.address
            restaurant.opening_hours = opening_hours or existing.opening_hours
            restaurant.category = category or existing.category
            restaurant.scraped_at = datetime.datetime.utcnow()
            restaurant.menu_items.clear()
            restaurant.amenities.clear()
            restaurant.images.clear()
        else:
            restaurant = models.Restaurant(
                name=name, phone=phone or "", whatsapp=whatsapp or "", address=address or "",
                jd_url=source_url, category=category or "", opening_hours=opening_hours or ""
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
def get_restaurants(db: Session = Depends(get_db)):
    restaurants = db.query(models.Restaurant).options(
        selectinload(models.Restaurant.images),
        selectinload(models.Restaurant.menu_items),
        selectinload(models.Restaurant.amenities)
    ).all()
    result = []
    for r in restaurants:
        primary_img = next((img.image_path for img in r.images if img.is_primary), None)
        if not primary_img and r.images: primary_img = r.images[0].image_path
            
        menu_list = [{"name": m.name, "price": m.price, "is_veg": m.is_veg} for m in r.menu_items]
        amenities_list = [{"category": a.category, "value": a.value} for a in r.amenities]
        images_list = [img.image_path for img in r.images]
        
        result.append({
            "id": r.id, "name": r.name, "phone": r.phone, "whatsapp": r.whatsapp, "address": r.address,
            "jd_url": r.jd_url, "category": r.category, "opening_hours": r.opening_hours,
            "image_path": primary_img, "menu_items": menu_list, "amenities": amenities_list, "images": images_list
        })
    return result

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