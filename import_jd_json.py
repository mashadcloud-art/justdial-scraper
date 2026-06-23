import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "justdial.db")

# Parsed restaurant data from the JustDial JSON response
# Fields: (name, phone, address, category, opening_hours, jd_url, thumbnail)
RESTAURANTS = [
    {
        "name": "Hotel Shaan",
        "phone": "09961848982",
        "address": "Railway Station Road, Vidyanagar, Kasaragod",
        "category": "Restaurants",
        "opening_hours": "11:00 am - 11:00 pm",
        "jd_url": "https://www.justdial.com/DT-99CK4Y1S7HP",
        "thumbnail": "https://content.jdmagicbox.com/comp/def_content/restaurants/default-restaurants-9-250.jpg",
        "rating": "4",
        "area": "Vidyanagar",
        "city": "Kasaragod",
    },
    {
        "name": "Ksd Restaurant",
        "phone": "09020917979",
        "address": "Chengala, Kerala, Nalamile, Kasaragod",
        "category": "Restaurants",
        "opening_hours": "8:00 am - 10:00 pm",
        "jd_url": "https://www.justdial.com/DT-99W82VXUYUN",
        "thumbnail": "https://content.jdmagicbox.com/comp/def_content_category/restaurants/photo-1497644083578-611b798c60f3-restaurants-6-h85ts-250.jpg",
        "rating": "4",
        "area": "Nalamile",
        "city": "Kasaragod",
    },
    {
        "name": "Arabian Food Box",
        "phone": "09072071525",
        "address": "BC Road, Sathyabhama Colony, Kasaragod",
        "category": "Restaurants",
        "opening_hours": "10:00 am - 11:00 pm",
        "jd_url": "https://www.justdial.com/DT-99A118X2V5H",
        "thumbnail": "https://content.jdmagicbox.com/comp/def_content/restaurants/default-restaurants-1-250.jpg",
        "rating": "4",
        "area": "Sathyabhama Colony",
        "city": "Kasaragod",
    },
    {
        "name": "Shreejith Kitchen",
        "phone": "",
        "address": "Kelu Gudde Cross Road, Kelugudde, Kasaragod",
        "category": "Restaurants",
        "opening_hours": "11:00 am - 11:00 pm",
        "jd_url": "https://www.justdial.com/DT-99EICR9TMYM",
        "thumbnail": "https://content.jdmagicbox.com/comp/def_content/restaurants/default-restaurants-8-250.jpg",
        "rating": "4",
        "area": "Kelugudde",
        "city": "Kasaragod",
    },
    {
        "name": "Chandragiri Live Fish Fry",
        "phone": "07722844494",
        "address": "Near Kadavath Road, Chamnad, Kasaragod",
        "category": "Sea Food",
        "opening_hours": "12:00 pm - 11:00 pm",
        "jd_url": "https://www.justdial.com/DT-99942CLQYKY",
        "thumbnail": "https://content.jdmagicbox.com/v2/comp/kasaragod/b5/9999p4994.4994.250808200330.e6b5/catalogue/chandragiri-live-fish-fry-chamnad-kasaragod-restaurants-nx54z63zlw-250.jpg",
        "rating": "3.5",
        "area": "Chamnad",
        "city": "Kasaragod",
    },
    {
        "name": "Khaleej Sea Foodland",
        "phone": "09895804445",
        "address": "Anangoor Choori, Cheroor, Kasaragod",
        "category": "Sea Food",
        "opening_hours": "7:00 am - 12:00 am",
        "jd_url": "https://www.justdial.com/DT-99E2AYUMUQM",
        "thumbnail": "https://content.jdmagicbox.com/comp/kasaragod/j7/9999p4994.4994.180907211705.c6j7/catalogue/khaleej-sea-foodland-kasaragod-restaurants-1j1vcus04m-250.jpg",
        "rating": "3.5",
        "area": "Cheroor",
        "city": "Kasaragod",
    },
    {
        "name": "Hotel Sinan",
        "phone": "09539749425",
        "address": "Muttathody, Kasaragod",
        "category": "Restaurants",
        "opening_hours": "11:00 am - 11:00 pm",
        "jd_url": "https://www.justdial.com/DT-99226YAIIQQ",
        "thumbnail": "https://content.jdmagicbox.com/comp/kasaragod/g5/9999p4994.4994.180327224643.f7g5/catalogue/hotel-sinan-muttathody-kasaragod-restaurants-rewdr-250.jpg",
        "rating": "3",
        "area": "Muttathody",
        "city": "Kasaragod",
    },
    {
        "name": "Hotel Udayagiri",
        "phone": "",
        "address": "Vidyanagar, Sathyabhama Colony, Kasaragod",
        "category": "Restaurants",
        "opening_hours": "11:00 am - 11:00 pm",
        "jd_url": "https://www.justdial.com/DT-99VFPPI16QZ",
        "thumbnail": "https://content.jdmagicbox.com/comp/def_content/restaurants/default-restaurants-9-250.jpg",
        "rating": "3",
        "area": "Sathyabhama Colony",
        "city": "Kasaragod",
    },
    {
        "name": "Life Line Hotel",
        "phone": "",
        "address": "Estate Road, Sathyabhama Colony, Kasaragod",
        "category": "Restaurants",
        "opening_hours": "11:00 am - 11:00 pm",
        "jd_url": "https://www.justdial.com/DT-99RJQ2VPMXN",
        "thumbnail": "https://content.jdmagicbox.com/comp/def_content/restaurants/default-restaurants-5-250.jpg",
        "rating": "3",
        "area": "Sathyabhama Colony",
        "city": "Kasaragod",
    },
    {
        "name": "Kallum Kadav",
        "phone": "",
        "address": "Perumbala, Kasaragod",
        "category": "Restaurants",
        "opening_hours": "",
        "jd_url": "https://www.justdial.com/DT-99IOKNJP5V2",
        "thumbnail": "https://content.jdmagicbox.com/comp/def_content/restaurants/default-restaurants-5-250.jpg",
        "rating": "5",
        "area": "Perumbala",
        "city": "Kasaragod",
    },
]

def import_restaurants():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    inserted = 0
    skipped = 0
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    for r in RESTAURANTS:
        # Check if already exists by name
        c.execute("SELECT id FROM restaurants WHERE name = ?", (r["name"],))
        existing = c.fetchone()
        if existing:
            print(f"  SKIP (already exists): {r['name']}")
            skipped += 1
            continue

        c.execute("""
            INSERT INTO restaurants (name, phone, whatsapp, address, jd_url, category, opening_hours, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["name"],
            r["phone"],
            r["phone"],   # use same number for whatsapp if available
            r["address"],
            r["jd_url"],
            r["category"],
            r["opening_hours"],
            now
        ))
        rest_id = c.lastrowid

        # Insert thumbnail as primary image
        if r.get("thumbnail"):
            c.execute("""
                INSERT INTO restaurant_images (restaurant_id, image_path, category, is_primary)
                VALUES (?, ?, ?, ?)
            """, (rest_id, r["thumbnail"], "general", 1))

        print(f"  INSERTED: {r['name']} (ID: {rest_id}) | {r['city']} - {r['area']} | Rating: {r['rating']}")
        inserted += 1

    conn.commit()
    conn.close()

    print(f"\n✅ Done! Inserted: {inserted} | Skipped: {skipped}")

if __name__ == "__main__":
    print(f"Importing {len(RESTAURANTS)} restaurants from JustDial JSON...\n")
    import_restaurants()
