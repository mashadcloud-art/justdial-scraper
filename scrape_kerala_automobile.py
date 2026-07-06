"""
Mass Scraping Automation for Kerala Automobile & Transport Categories.
Iterates through all 14 districts of Kerala and scrapes car, taxi, second hand deals, and garages.
Uses a JSON checkpoint file to resume progress.
"""

import os
import sys
import json
import time
import random
import logging

# Add workspace root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jd_api_scraper import scrape_jwt_city

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mass_auto_scraper")

# List of Kerala Districts
DISTRICTS = [
    "Wayanad", "Kasaragod", "Kannur", "Kozhikode", "Malappuram", 
    "Palakkad", "Thrissur", "Ernakulam", "Idukki", "Kottayam", 
    "Alappuzha", "Pathanamthitta", "Kollam", "Thiruvananthapuram"
]

# Automobile & Transport categories requested by user
CATEGORIES = [
    "Taxi Services",
    "Car Rentals",
    "Used Car Dealers",
    "Used Motorcycle Dealers",
    "Car Garages"
]

CHECKPOINT_FILE = os.path.join("data", "scrape_checkpoint_automobile.json")

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
    logger.info("🚗 Starting Mass Kerala Automobile & Transport Scraper...")
    checkpoint = load_checkpoint()

    total_inserted = 0
    total_updated = 0

    for district in DISTRICTS:
        for category in CATEGORIES:
            key = f"{district.lower()}|{category.lower()}"
            if checkpoint.get(key) == "done":
                logger.info(f"✅ [CHECKPOINT] Already completed {category} in {district}. Skipping.")
                continue

            logger.info(f"\n🚀 Running: District={district} | Category={category}...")
            
            try:
                # Run the scraper
                # pages=10 to match 'deep search' requested by user
                ins, upd = scrape_jwt_city(
                    district=district,
                    category=category,
                    pages=10,
                    limit=10,
                    dry_run=False,
                    subcategories=False,
                    use_proxy=(sys.platform != "win32") # Auto-enable proxy on Linux cloud VPS
                )
                
                total_inserted += ins
                total_updated += upd
                
                # Mark as completed
                checkpoint[key] = "done"
                save_checkpoint(checkpoint)
                logger.info(f"💾 Saved progress: {category} in {district} is marked done.")
                
            except Exception as e:
                logger.error(f"❌ Error scraping {category} in {district}: {e}")
                # Wait before next iteration if there is an error
                time.sleep(5)

            # Polite delay between category runs to prevent rate-limiting/blocking
            delay = random.uniform(3.0, 7.0)
            logger.info(f"Sleeping for {delay:.2f}s before next run...")
            time.sleep(delay)

    logger.info(f"\n🎉 Mass Scraping Completed! Total Inserted: {total_inserted} | Total Updated: {total_updated}")

if __name__ == "__main__":
    main()
