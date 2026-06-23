import json
import os
import sys
from datetime import datetime

# Ensure Python can find the modules in the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app import models
from app.scraper.api_scraper import parse_api_row

demo_json_string = """{
  "results": {
    "columns": ["docid", "name", "phone", "rating", "review_count", "address", "thumbnail", "latitude", "longitude"],
    "data": [
      ["12345", "Super Emulator Burger Joint", "+919876543210", "4.8", "120", "123 Test St, Ernakulam", "https://via.placeholder.com/150", "9.9", "76.2"],
      ["67890", "Mobile Magic Cafe", "+918765432109", "4.5", "85", "456 Mobile Ave, Kochi", "https://via.placeholder.com/150", "9.8", "76.3"]
    ]
  }
}"""

data = json.loads(demo_json_string)
district = "Ernakulam"

db = SessionLocal()

# Parse format
columns = data["results"]["columns"]
rows = data["results"]["data"]
col_map = {col: i for i, col in enumerate(columns)}

restaurants = []
for row in rows:
    r = parse_api_row(row, col_map)
    if r:
        restaurants.append(r)

print(f"Parsed {len(restaurants)} restaurants from JSON:")

for r in restaurants:
    name = r["name"]
    phone = r.get("phone", "")
    address = r.get("address", "")
    source_url = r.get("source_url", "")
    if not source_url:
        source_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{name.replace(' ', '-')}"
    category = r.get("category", "")
    
    # Check if duplicate
    existing = db.query(models.Restaurant).filter(models.Restaurant.name == name).first()
    if existing:
        print(f"Updating: {name}")
        existing.phone = phone or existing.phone
        existing.address = address or existing.address
        existing.category = category or existing.category
        existing.district = district
        existing.scraped_at = datetime.utcnow()
    else:
        print(f"Inserting: {name}")
        new_res = models.Restaurant(
            name=name,
            phone=phone,
            address=address,
            jd_url=source_url,
            category=category,
            district=district
        )
        db.add(new_res)

db.commit()
db.close()
print("Direct DB Ingestion Complete!")
