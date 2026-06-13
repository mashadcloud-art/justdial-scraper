import sys
import os
import shutil
import datetime
import json
import traceback
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.database import get_db
from app import models

router = APIRouter(prefix="/api/v1", tags=["sync"])
UPLOAD_DIR = "uploaded_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
            restaurant.scraped_at = datetime.datetime.utcnow()
            restaurant.menu_items.clear()
            restaurant.amenities.clear()
            restaurant.images.clear()
        else:
            restaurant = models.Restaurant(
                name=name, phone=phone or "", whatsapp=whatsapp or "", address=address or "",
                jd_url=source_url, opening_hours=opening_hours or ""
            )
            db.add(restaurant)
            db.flush() 
            
        restaurant_id = restaurant.id

        if menu_json:
            try:
                for item in json.loads(menu_json):
                    db.add(models.MenuItem(restaurant_id=restaurant_id, name=str(item.get('name', '')), price=str(item.get('price', '0')), is_veg=bool(item.get('is_veg', True))))
            except: pass

        if amenities_json:
            try:
                amenities_data = json.loads(amenities_json)
                if isinstance(amenities_data, dict):
                    for category, values in amenities_data.items():
                        if isinstance(values, list):
                            for val in values:
                                db.add(models.Amenity(restaurant_id=restaurant_id, category=str(category), value=str(val)))
            except: pass

        categories = []
        if image_categories:
            try: categories = json.loads(image_categories)
            except: pass

        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip()
        for i, img_file in enumerate(images):
            if img_file and img_file.filename:
                cat = categories[i] if i < len(categories) else "general"
                safe_cat = "".join(c for c in cat if c.isalnum()).rstrip() or "general"
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                filename = f"{safe_name}_{safe_cat}_{i}_{timestamp}.jpg"
                image_path = os.path.join(UPLOAD_DIR, filename)
                with open(image_path, "wb") as buffer:
                    shutil.copyfileobj(img_file.file, buffer)
                db.add(models.RestaurantImage(restaurant_id=restaurant_id, image_path=image_path, category=cat, is_primary=(i == 0)))

        db.commit()
        return {"message": "Success", "restaurant_id": restaurant_id}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. GET ALL RESTAURANTS (Existing)
# ==========================================
@router.get("/restaurants")
def get_restaurants(db: Session = Depends(get_db)):
    restaurants = db.query(models.Restaurant).all()
    result = []
    for r in restaurants:
        primary_img = next((img.image_path for img in r.images if img.is_primary), None)
        if not primary_img and r.images: primary_img = r.images[0].image_path
            
        menu_list = [{"name": m.name, "price": m.price, "is_veg": m.is_veg} for m in r.menu_items]
        amenities_list = [{"category": a.category, "value": a.value} for a in r.amenities]
        
        result.append({
            "id": r.id, "name": r.name, "phone": r.phone, "whatsapp": r.whatsapp, "address": r.address,
            "jd_url": r.jd_url, "opening_hours": r.opening_hours,
            "image_path": primary_img, "menu_items": menu_list, "amenities": amenities_list
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
# 5. NEW: CLEAR ALL DATA (Danger Zone)
# ==========================================
@router.post("/clear-all")
def clear_all(db: Session = Depends(get_db)):
    db.query(models.MenuItem).delete()
    db.query(models.Amenity).delete()
    db.query(models.RestaurantImage).delete()
    db.query(models.Restaurant).delete()
    db.commit()
    return {"status": "success"}