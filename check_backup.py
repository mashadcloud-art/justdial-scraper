import sqlite3
import os

DATA_DB = os.path.join("data", "justdial.db")

conn = sqlite3.connect(DATA_DB)
c = conn.cursor()

# Overall counts
c.execute("SELECT COUNT(*) FROM restaurants")
total = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM restaurant_images")
images = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM menu_items")
menus = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM amenities")
amenities = c.fetchone()[0]

print("=" * 50)
print(f"  TOTAL RESTAURANTS : {total}")
print(f"  TOTAL IMAGES      : {images}")
print(f"  TOTAL MENU ITEMS  : {menus}")
print(f"  TOTAL AMENITIES   : {amenities}")
print("=" * 50)

# Breakdown by city/district
print("\nBreakdown by city (address field):")
c.execute("""
    SELECT 
        LOWER(TRIM(district)) as city, 
        COUNT(*) as cnt 
    FROM restaurants 
    GROUP BY city 
    ORDER BY cnt DESC
    LIMIT 30
""")
rows = c.fetchall()
for row in rows:
    print(f"  {row[0] or '(no district)':<30} {row[1]} restaurants")

# DB file size
size_mb = os.path.getsize(DATA_DB) / (1024 * 1024)
print(f"\n  DB File Size: {size_mb:.2f} MB")
print(f"  DB Path: {os.path.abspath(DATA_DB)}")

conn.close()
