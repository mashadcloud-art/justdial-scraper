"""
fix_categories_in_supabase.py
Moves JustDial cuisine tags from `category` to `subcategory` for existing data.
Run: python fix_categories_in_supabase.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SUPABASE_URL = "postgresql://postgres:HEERnuh%402025@db.qdsjbfhjzyypfyryjqxp.supabase.co:5432/postgres"
engine = create_engine(SUPABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
db = Session()

# Known cuisine/tag keywords from JustDial
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

try:
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM restaurants")).scalar()
        print(f"Total records: {total}")

    # Load all records
    rows = db.execute(text("SELECT id, category, subcategory FROM restaurants")).fetchall()
    
    to_fix = []
    for row in rows:
        rid, category, subcategory = row[0], row[1] or "", row[2] or ""
        if looks_like_cuisine_tags(category) and category != "Restaurants":
            to_fix.append((rid, "Restaurants", category))
    
    print(f"Records to fix: {len(to_fix)} out of {len(rows)}")
    
    if to_fix:
        fixed = 0
        BATCH = 200
        for i, (rid, new_cat, new_subcat) in enumerate(to_fix):
            db.execute(
                text("UPDATE restaurants SET category = :cat, subcategory = :sub WHERE id = :id"),
                {"cat": new_cat, "sub": new_subcat, "id": rid}
            )
            fixed += 1
            if fixed % BATCH == 0:
                db.commit()
                pct = round((fixed / len(to_fix)) * 100, 1)
                print(f"  [{pct}%] Fixed {fixed}/{len(to_fix)}...")
        
        db.commit()
        print(f"\nDONE! Fixed {fixed} records.")
        print("  category   -> 'Restaurants' (or parent type)")
        print("  subcategory -> JustDial cuisine tags (Punjabi, South Indian, etc.)")
    else:
        print("Nothing to fix - all records look correct already.")

    # Show sample
    sample = db.execute(text(
        "SELECT name, category, subcategory FROM restaurants LIMIT 5"
    )).fetchall()
    print("\nSample records after fix:")
    for r in sample:
        print(f"  [{r[1]}] [{r[2]}] {r[0]}")

except Exception as e:
    db.rollback()
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
finally:
    db.close()
