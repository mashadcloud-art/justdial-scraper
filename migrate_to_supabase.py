"""
migrate_to_supabase.py  (FIXED - includes images, menu_items, amenities)
Run: python migrate_to_supabase.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import selectinload

# ── LOCAL SQLite ──────────────────────────────────────────────
LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "justdial.db")
LOCAL_URL = f"sqlite:///{LOCAL_DB_PATH.replace(os.sep, '/')}"
local_engine = create_engine(LOCAL_URL, connect_args={"check_same_thread": False})
LocalSession = sessionmaker(bind=local_engine)

# ── SUPABASE (cloud) ───────────────────────────────────────────
SUPABASE_URL = "postgresql://postgres:HEERnuh%402025@db.qdsjbfhjzyypfyryjqxp.supabase.co:5432/postgres"
cloud_engine = create_engine(SUPABASE_URL, pool_pre_ping=True, pool_size=3, max_overflow=5)
CloudSession = sessionmaker(bind=cloud_engine)

from app.scraper.emulator_parser import get_state_from_district
import app.models as models
from app.database import Base

# Create tables on cloud if not exist
Base.metadata.create_all(bind=cloud_engine)

local_db  = LocalSession()
cloud_db  = CloudSession()

try:
    print("Clearing partial Supabase data to re-migrate cleanly...")
    cloud_db.execute(text("DELETE FROM amenities"))
    cloud_db.execute(text("DELETE FROM menu_items"))
    cloud_db.execute(text("DELETE FROM restaurant_images"))
    cloud_db.execute(text("DELETE FROM restaurants"))
    cloud_db.commit()
    print("Cleared. Starting fresh migration...")

    # Eagerly load ALL related data from SQLite in one query
    restaurants = (
        local_db.query(models.Restaurant)
        .options(
            selectinload(models.Restaurant.images),
            selectinload(models.Restaurant.menu_items),
            selectinload(models.Restaurant.amenities),
        )
        .all()
    )
    total = len(restaurants)
    print(f"Found {total} restaurants in local SQLite. Migrating with all details...")

    migrated = 0
    BATCH = 50  # commit every 50 records

    for r in restaurants:
        state = r.state or get_state_from_district(r.district or "")

        new_r = models.Restaurant(
            name=r.name,
            address=r.address,
            phone=r.phone,
            whatsapp=r.whatsapp,
            jd_url=r.jd_url,
            category=r.category,
            subcategory=getattr(r, "subcategory", None),
            opening_hours=r.opening_hours,
            district=r.district,
            state=state,
            latitude=r.latitude,
            longitude=r.longitude,
            scraped_at=r.scraped_at,
        )
        cloud_db.add(new_r)
        cloud_db.flush()  # get new_r.id

        # ── Images ──────────────────────────────────────────
        for img in r.images:
            cloud_db.add(models.RestaurantImage(
                restaurant_id=new_r.id,
                image_path=img.image_path,
                category=img.category,
                is_primary=img.is_primary,
            ))

        # ── Menu Items ───────────────────────────────────────
        for m in r.menu_items:
            cloud_db.add(models.MenuItem(
                restaurant_id=new_r.id,
                name=m.name,
                price=m.price,
                is_veg=m.is_veg,
            ))

        # ── Amenities ────────────────────────────────────────
        for a in r.amenities:
            cloud_db.add(models.Amenity(
                restaurant_id=new_r.id,
                category=a.category,
                value=a.value,
            ))

        migrated += 1
        if migrated % BATCH == 0:
            cloud_db.commit()
            pct = round((migrated / total) * 100, 1)
            print(f"  [{pct}%] Migrated {migrated}/{total} restaurants...")

    cloud_db.commit()
    print(f"\n=== MIGRATION COMPLETE ===")
    print(f"  Restaurants : {migrated}")

    # Quick count verification
    with cloud_engine.connect() as conn:
        r_count  = conn.execute(text("SELECT COUNT(*) FROM restaurants")).scalar()
        img_count = conn.execute(text("SELECT COUNT(*) FROM restaurant_images")).scalar()
        menu_count = conn.execute(text("SELECT COUNT(*) FROM menu_items")).scalar()
        amn_count  = conn.execute(text("SELECT COUNT(*) FROM amenities")).scalar()
    print(f"  Restaurants in Supabase  : {r_count}")
    print(f"  Images in Supabase       : {img_count}")
    print(f"  Menu Items in Supabase   : {menu_count}")
    print(f"  Amenities in Supabase    : {amn_count}")

except Exception as e:
    cloud_db.rollback()
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    local_db.close()
    cloud_db.close()
