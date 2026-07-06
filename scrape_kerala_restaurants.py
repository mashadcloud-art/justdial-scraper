"""
Scraping Automation for Kerala Restaurants.
Scrapes the "Restaurants" category across remaining Kerala districts:
Excluding Kasaragod, Kannur, and Kozhikode.
"""

import os
import sys
import json
import time
import random
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jd_api_scraper import scrape_jwt_city

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("restaurants_scraper")

# Kerala districts excluding Kasaragod, Kannur, and Kozhikode
DISTRICTS = [
    "Wayanad", "Malappuram", "Palakkad", "Thrissur", "Ernakulam", 
    "Idukki", "Kottayam", "Alappuzha", "Pathanamthitta", "Kollam", 
    "Thiruvananthapuram"
]

CATEGORY = "Restaurants"
CHECKPOINT_FILE = os.path.join("data", "scrape_checkpoint_restaurants.json")

def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load checkpoint file: {e}")
    return {}

def save_checkpoint(checkpoint: dict):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    try:
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")

def main():
    logger.info("🍔 Starting Kerala Restaurants Scraper...")
    checkpoint = load_checkpoint()

    total_inserted = 0
    total_updated = 0

    for district in DISTRICTS:
        key = f"{district.lower()}|{CATEGORY.lower()}"
        if checkpoint.get(key) == "done":
            logger.info(f"✅ [CHECKPOINT] Already completed {CATEGORY} in {district}. Skipping.")
            continue

        logger.info(f"\n🚀 Running: District={district} | Category={CATEGORY}...")
        
        try:
            ins, upd = scrape_jwt_city(
                district=district,
                category=CATEGORY,
                pages=10,
                limit=10,
                dry_run=False,
                subcategories=False,
                use_proxy=(sys.platform != "win32") # Auto-enable proxy on Linux cloud VPS
            )
            
            total_inserted += ins
            total_updated += upd
            
            checkpoint[key] = "done"
            save_checkpoint(checkpoint)
            logger.info(f"💾 Saved progress: {CATEGORY} in {district} marked done.")
            
        except Exception as e:
            logger.error(f"❌ Error scraping {CATEGORY} in {district}: {e}")
            time.sleep(5)

        delay = random.uniform(3.0, 7.0)
        logger.info(f"Sleeping for {delay:.2f}s before next run...")
        time.sleep(delay)

    logger.info(f"\n🎉 Restaurants Scraping Completed! Total Inserted: {total_inserted} | Total Updated: {total_updated}")

if __name__ == "__main__":
    main()
