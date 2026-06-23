import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Connect to the ACTUAL database in the data folder
conn = sqlite3.connect("data/justdial.db")
cursor = conn.cursor()

# Get restaurant details
cursor.execute("SELECT id, name, jd_url FROM restaurants WHERE name LIKE '%Jithu%'")
restaurants = cursor.fetchall()
print(f"Found {len(restaurants)} matching restaurants in data/justdial.db:")
for r in restaurants:
    r_id, r_name, r_url = r
    print(f"\nID: {r_id} | Name: {r_name} | URL: {r_url}")
    
    # Get images
    cursor.execute("SELECT id, image_path, category, is_primary FROM restaurant_images WHERE restaurant_id = ?", (r_id,))
    images = cursor.fetchall()
    print(f"  Images ({len(images)}):")
    for img in images:
        print(f"    ID: {img[0]} | Path/URL: {img[1]} | Category: {img[2]} | Primary: {img[3]}")
        
    # Get menu items
    cursor.execute("SELECT id, name, price, is_veg FROM menu_items WHERE restaurant_id = ?", (r_id,))
    items = cursor.fetchall()
    print(f"  Menu Items ({len(items)}):")
    for item in items[:15]:
         print(f"    ID: {item[0]} | Name: {item[1]} | Price: {item[2]} | Veg: {item[3]}")
    if len(items) > 15:
         print(f"    ... and {len(items)-15} more items.")

conn.close()
