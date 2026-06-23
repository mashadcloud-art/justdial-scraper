"""
fast_migrate_to_supabase.py
Optimized high-performance migration script for Supabase.
Applies:
1. Auto-assign State from District
2. Extract Place from Address (e.g. Kuttikkanam)
3. Segregate Category & Subcategory (e.g. Restaurants -> Fast Food / Punjabi)
4. Classify building/complex categories (e.g. Maryam Trade Center -> Trade Centers)
5. High-speed Bulk Insertion
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Local SQLite
LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "justdial.db")
LOCAL_URL = f"sqlite:///{LOCAL_DB_PATH.replace(os.sep, '/')}"
local_engine = create_engine(LOCAL_URL)
LocalSession = sessionmaker(bind=local_engine)

# Supabase
SUPABASE_URL = "postgresql://postgres:HEERnuh%402025@db.qdsjbfhjzyypfyryjqxp.supabase.co:5432/postgres"
cloud_engine = create_engine(SUPABASE_URL, pool_pre_ping=True)
CloudSession = sessionmaker(bind=cloud_engine)

from app.scraper.emulator_parser import get_state_from_district, extract_place_from_address, detect_category_from_name
import app.models as models
from app.database import Base

# Create tables on cloud if they do not exist
Base.metadata.create_all(bind=cloud_engine)

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

local_db = LocalSession()
cloud_db = CloudSession()

try:
    print("Clearing existing cloud database tables...")
    cloud_db.execute(text("DELETE FROM amenities"))
    cloud_db.execute(text("DELETE FROM menu_items"))
    cloud_db.execute(text("DELETE FROM restaurant_images"))
    cloud_db.execute(text("DELETE FROM restaurants"))
    cloud_db.commit()
    print("Cloud database cleared.")

    # 1. Fetch restaurants from SQLite
    print("Fetching restaurants from local SQLite...")
    sqlite_restaurants = local_db.execute(text(
        "SELECT id, name, address, phone, whatsapp, jd_url, category, subcategory, "
        "opening_hours, district, state, latitude, longitude, scraped_at "
        "FROM restaurants"
    )).fetchall()
    
    total_r = len(sqlite_restaurants)
    print(f"Loaded {total_r} restaurants from SQLite. Processing and preparing bulk insert...")
    
    restaurant_mappings = []
    for r in sqlite_restaurants:
        r_id, name, address, phone, whatsapp, jd_url, raw_category, subcat, opening_hours, district, state, latitude, longitude, scraped_at = r
        
        # State auto-assignment
        state_val = state or get_state_from_district(district or "")
        
        # Place/locality extraction (computed dynamically since it is not in the source SQLite table)
        place_val = extract_place_from_address(address or "", district or "")
        
        # Category/subcategory splitting
        category, subcategory = process_category_subcategory(raw_category)
        if subcat:
            subcategory = subcat
            
        # Detect if business name contains building/complex keywords
        category = detect_category_from_name(name, category)
        
        restaurant_mappings.append({
            "id": r_id,
            "name": name,
            "address": address,
            "phone": phone,
            "whatsapp": whatsapp,
            "jd_url": jd_url,
            "category": category,
            "subcategory": subcategory,
            "opening_hours": opening_hours,
            "district": district,
            "place": place_val,
            "state": state_val,
            "latitude": latitude,
            "longitude": longitude,
            "scraped_at": scraped_at
        })
        
    # Bulk insert restaurants
    print("Bulk inserting restaurants into Supabase...")
    BATCH_SIZE = 1000
    for i in range(0, len(restaurant_mappings), BATCH_SIZE):
        batch = restaurant_mappings[i:i+BATCH_SIZE]
        cloud_db.execute(
            models.Restaurant.__table__.insert(),
            batch
        )
        print(f"  Inserted {min(i+BATCH_SIZE, len(restaurant_mappings))}/{len(restaurant_mappings)} restaurants...")
    cloud_db.commit()
    print("Restaurants bulk insert complete!")

    # 2. Fetch images from SQLite
    print("Fetching images from local SQLite...")
    sqlite_images = local_db.execute(text(
        "SELECT id, restaurant_id, image_path, category, is_primary "
        "FROM restaurant_images"
    )).fetchall()
    
    total_img = len(sqlite_images)
    print(f"Loaded {total_img} images from SQLite. Processing and preparing bulk insert...")
    
    image_mappings = []
    for img in sqlite_images:
        img_id, r_id, image_path, category, is_primary = img
        image_mappings.append({
            "id": img_id,
            "restaurant_id": r_id,
            "image_path": image_path,
            "category": category,
            "is_primary": bool(is_primary)
        })
        
    # Bulk insert images
    print("Bulk inserting images into Supabase...")
    for i in range(0, len(image_mappings), BATCH_SIZE):
        batch = image_mappings[i:i+BATCH_SIZE]
        cloud_db.execute(
            models.RestaurantImage.__table__.insert(),
            batch
        )
        print(f"  Inserted {min(i+BATCH_SIZE, len(image_mappings))}/{len(image_mappings)} images...")
    cloud_db.commit()
    print("Images bulk insert complete!")

    # 3. Reset PostgreSQL sequences
    print("Resetting PostgreSQL database ID sequences...")
    cloud_db.execute(text("SELECT setval(pg_get_serial_sequence('restaurants', 'id'), coalesce(max(id), 1)) FROM restaurants"))
    cloud_db.execute(text("SELECT setval(pg_get_serial_sequence('restaurant_images', 'id'), coalesce(max(id), 1)) FROM restaurant_images"))
    cloud_db.commit()
    print("Sequences reset successfully.")
    
    print("\n=== MIGRATION AND DATA QUALITY CLEANUP COMPLETED SUCCESSFULLY ===")
    
except Exception as e:
    cloud_db.rollback()
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    local_db.close()
    cloud_db.close()
