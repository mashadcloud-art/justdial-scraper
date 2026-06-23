import sqlite3
import os

ROOT_DB = "justdial.db"
DATA_DB = os.path.join("data", "justdial.db")

# The 10 Kasaragod restaurants we inserted (IDs 5-14 in root DB)
src = sqlite3.connect(ROOT_DB)
dst = sqlite3.connect(DATA_DB)
sc = src.cursor()
dc = dst.cursor()

# Fetch the 10 Kasaragod restaurants from root DB
sc.execute("SELECT name, phone, whatsapp, address, jd_url, category, opening_hours, scraped_at FROM restaurants WHERE id >= 5")
restaurants = sc.fetchall()

inserted = 0
skipped = 0

for r in restaurants:
    name = r[0]
    # Check if already exists in data DB
    dc.execute("SELECT id FROM restaurants WHERE name = ?", (name,))
    if dc.fetchone():
        print(f"  SKIP (exists): {name}")
        skipped += 1
        continue

    dc.execute("""
        INSERT INTO restaurants (name, phone, whatsapp, address, jd_url, category, opening_hours, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, r)
    new_id = dc.lastrowid

    # Fetch and migrate its images
    sc.execute("SELECT image_path, category, is_primary FROM restaurant_images WHERE restaurant_id = (SELECT id FROM restaurants WHERE name = ?)", (name,))
    images = sc.fetchall()
    for img in images:
        dc.execute("""
            INSERT INTO restaurant_images (restaurant_id, image_path, category, is_primary)
            VALUES (?, ?, ?, ?)
        """, (new_id, img[0], img[1], img[2]))

    print(f"  INSERTED: {name} (new ID: {new_id}, images: {len(images)})")
    inserted += 1

dst.commit()
src.close()
dst.close()

print(f"\n✅ Migration done! Inserted: {inserted} | Skipped: {skipped}")

# Verify final count
conn = sqlite3.connect(DATA_DB)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM restaurants")
print(f"Total restaurants in data/justdial.db: {c.fetchone()[0]}")
conn.close()
