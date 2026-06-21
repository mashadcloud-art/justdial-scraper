import json
import os
import re
import requests
from typing import List, Dict, Any
from app.scraper.logger import log
from app.scraper.api_scraper import clean_phone, parse_api_row, upload_to_api

def upload_to_db_directly(restaurant: Dict, district: str) -> bool:
    from app.database import SessionLocal
    from app import models
    from datetime import datetime
    
    db = SessionLocal()
    try:
        name = restaurant["name"]
        phone = restaurant.get("phone", "")
        address = restaurant.get("address", "")
        source_url = restaurant.get("source_url", "")
        if not source_url:
            source_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{name.replace(' ', '-')}"
        category = restaurant.get("category", "")
        
        latitude = restaurant.get("latitude", "")
        longitude = restaurant.get("longitude", "")
        opening_hours = restaurant.get("opening_hours", "")
        
        existing = db.query(models.Restaurant).filter(models.Restaurant.name == name).first()
        if existing:
            restaurant_obj = existing
            restaurant_obj.phone = phone or existing.phone
            restaurant_obj.address = address or existing.address
            restaurant_obj.category = category or existing.category
            restaurant_obj.district = district or existing.district
            restaurant_obj.latitude = latitude or existing.latitude
            restaurant_obj.longitude = longitude or existing.longitude
            restaurant_obj.opening_hours = opening_hours or existing.opening_hours
            restaurant_obj.scraped_at = datetime.utcnow()
        else:
            restaurant_obj = models.Restaurant(
                name=name,
                phone=phone,
                address=address,
                jd_url=source_url,
                category=category,
                district=district,
                latitude=latitude,
                longitude=longitude,
                opening_hours=opening_hours
            )
            db.add(restaurant_obj)
            db.flush()
            
        # Add all images
        images = restaurant.get("images", [])
        for idx, img_path in enumerate(images):
            img_exists = db.query(models.RestaurantImage).filter(
                models.RestaurantImage.restaurant_id == restaurant_obj.id,
                models.RestaurantImage.image_path == img_path
            ).first()
            if not img_exists:
                db.add(models.RestaurantImage(
                    restaurant_id=restaurant_obj.id,
                    image_path=img_path,
                    category="general",
                    is_primary=(idx == 0)
                ))
                
        db.commit()
        return True
    except Exception as e:
        print(f"Direct DB save error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def process_emulator_json(json_data: Any, district: str = "Unknown") -> int:
    """
    Parses intercepted JSON from the JustDial mobile app API and uploads 
    to our database. Returns the number of successfully uploaded restaurants.
    """
    if isinstance(json_data, dict) and "json_data" in json_data:
        district = json_data.get("district", district) or district
        json_data = json_data["json_data"]

    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            log("❌ Invalid JSON string provided to emulator parser.", ok=False)
            return 0
    else:
        data = json_data

    restaurants = []

    # Check if this is a HAR file export from HTTP Toolkit
    if "log" in data and "entries" in data["log"]:
        log("📦 Detected a full HAR file export. Scanning all requests...")
        success_count = 0
        for entry in data["log"]["entries"]:
            # Get the response text
            try:
                content_text = entry.get("response", {}).get("content", {}).get("text", "")
                if content_text and "results" in content_text:
                    # Attempt to parse this specific request's JSON
                    parsed_content = json.loads(content_text)
                    success_count += process_emulator_json(parsed_content, district)
            except Exception:
                pass
        return success_count

    # Parse standard mobile API format
    try:
        if "results" in data and isinstance(data["results"], dict) and "name" in data["results"]:
            # Single object format (e.g. detailed view)
            res = data["results"]
            parsed_res = {
                "name": res.get("name", ""),
                "phone": clean_phone(res.get("mobile", "")),
                "rating": res.get("rating", ""),
                "review_count": res.get("totJdReviews", ""),
                "address": res.get("address", ""),
                "thumbnail": res.get("jadoopic", ""),
                "latitude": res.get("complat", ""),
                "longitude": res.get("complong", ""),
                "url": res.get("Sharerating", "").strip()
            }
            if parsed_res["name"]:
                restaurants.append(parsed_res)
            log(f"📱 Emulator Parser found format: Single Object")
            
        elif "results" in data and "columns" in data["results"] and "data" in data["results"]:
            # Array format (e.g. search list)
            columns = data["results"]["columns"]
            rows = data["results"]["data"]
            log(f"📱 Emulator Parser found format: {len(columns)} columns, {len(rows)} rows")
            
            col_map = {col: i for i, col in enumerate(columns)}
            
            for row in rows:
                if not isinstance(row, list):
                    continue
                r = parse_api_row(row, col_map)
                if r:
                    restaurants.append(r)
    except Exception as e:
        log(f"❌ Error parsing emulator JSON: {e}", ok=False)
        return 0

    if not restaurants:
        log("⚠️ No restaurants found in the provided JSON.", ok=False)
        return 0

    log(f"📱 Extracted {len(restaurants)} restaurants from JSON. Uploading...")
    
    success_count = 0
    for res in restaurants:
        name = res.get("name", "Unknown")
        phone = res.get("phone", "")
        rating = res.get("rating", "")
        
        log(f"  ➜ {name} | Phone: {phone} | Rating: {rating}")
        
        if upload_to_db_directly(res, district):
            success_count += 1
            log(f"    ✅ Uploaded!")
        else:
            log(f"    ❌ Failed.", ok=False)

    log(f"🏁 Emulator JSON Processing Complete: {success_count}/{len(restaurants)} uploaded successfully.")
    return success_count
