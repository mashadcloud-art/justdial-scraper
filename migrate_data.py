import sys
import os
from tqdm import tqdm

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.database import Base, SessionLocal, get_db
from app import models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import settings

def migrate_data():
    """Migrate data from SQLite to PostgreSQL (optional)"""
    
    # Ask user if they want to migrate
    print("=== Data Migration Tool ===")
    print("This tool copies data from SQLite to your cloud database (PostgreSQL)")
    print("Make sure you've already updated config.py to use your cloud DB!")
    confirm = input("Do you want to continue? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("Cancelled.")
        return
    
    # First, get the old SQLite DB path
    old_db_path = os.path.join(project_root, "data", "justdial.db")
    old_db_url = f"sqlite:///{old_db_path.replace(os.sep, '/')}"
    print(f"Old SQLite DB: {old_db_url}")
    
    # Create engine for old SQLite DB
    old_engine = create_engine(old_db_url, connect_args={"check_same_thread": False})
    OldSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=old_engine)
    old_db = OldSessionLocal()
    
    # New DB session
    new_db = SessionLocal()
    
    try:
        # Step 1: Migrate Restaurants
        print("\nMigrating restaurants...")
        old_restaurants = old_db.query(models.Restaurant).all()
        for old_rest in tqdm(old_restaurants):
            # Create new restaurant
            new_rest = models.Restaurant(
                id=old_rest.id,
                name=old_rest.name,
                address=old_rest.address,
                phone=old_rest.phone,
                whatsapp=old_rest.whatsapp,
                jd_url=old_rest.jd_url,
                category=old_rest.category,
                opening_hours=old_rest.opening_hours,
                scraped_at=old_rest.scraped_at
            )
            new_db.add(new_rest)
            new_db.flush()
            
            # Migrate images
            for old_img in old_rest.images:
                new_img = models.RestaurantImage(
                    restaurant_id=new_rest.id,
                    image_path=old_img.image_path,
                    category=old_img.category,
                    is_primary=old_img.is_primary
                )
                new_db.add(new_img)
            
            # Migrate menu items
            for old_menu in old_rest.menu_items:
                new_menu = models.MenuItem(
                    restaurant_id=new_rest.id,
                    name=old_menu.name,
                    price=old_menu.price,
                    is_veg=old_menu.is_veg
                )
                new_db.add(new_menu)
            
            # Migrate amenities
            for old_amen in old_rest.amenities:
                new_amen = models.Amenity(
                    restaurant_id=new_rest.id,
                    category=old_amen.category,
                    value=old_amen.value
                )
                new_db.add(new_amen)
        
        # Step 2: Migrate Categories and Selected Categories
        print("\nMigrating categories...")
        old_cats = old_db.query(models.Category).all()
        for old_cat in old_cats:
            new_cat = models.Category(
                id=old_cat.id,
                name=old_cat.name,
                parent_category=old_cat.parent_category,
                sub_category=old_cat.sub_category,
                jd_url=old_cat.jd_url,
                is_active=old_cat.is_active,
                created_at=old_cat.created_at
            )
            new_db.add(new_cat)
        
        old_selected_cats = old_db.query(models.SelectedCategory).all()
        for old_sel in old_selected_cats:
            new_sel = models.SelectedCategory(
                id=old_sel.id,
                category_id=old_sel.category_id,
                city=old_sel.city,
                selected_at=old_sel.selected_at
            )
            new_db.add(new_sel)
        
        # Commit everything
        new_db.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        new_db.rollback()
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        old_db.close()
        new_db.close()

if __name__ == "__main__":
    migrate_data()
