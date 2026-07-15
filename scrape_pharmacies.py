import os
import sys
import json
import time
import random
import logging

# Add workspace root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from jd_api_scraper import scrape_jwt_city

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("pharmacies_scraper")

# All 14 districts in Kerala
districts_to_scrape = [
    "Alappuzha",
    "Ernakulam",
    "Idukki",
    "Kannur",
    "Kasaragod",
    "Kollam",
    "Kottayam",
    "Kozhikode",
    "Malappuram",
    "Palakkad",
    "Pathanamthitta",
    "Thiruvananthapuram",
    "Thrissur",
    "Wayanad"
]

# All pharmacy-related categories
categories = [
    "Chemists",
    "Pharmacies",
    "Medical Shops"
]

CHECKPOINT_FILE = os.path.join("data", "scrape_checkpoint_pharmacies_main.json")
FLAG_FILE = os.path.join("data", "scrape_stop.flag")

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

def check_stop_flag() -> bool:
    if os.path.exists(FLAG_FILE):
        logger.info("🛑 Stop flag detected! Pausing/stopping the scraping process.")
        return True
    return False

def clear_stop_flag():
    if os.path.exists(FLAG_FILE):
        try:
            os.remove(FLAG_FILE)
            logger.info("🧹 Existing stop flag cleared. Starting fresh run.")
        except Exception as e:
            logger.warning(f"Failed to clear stop flag: {e}")

def main():
    logger.info("💊 Starting Pharmacies Scraper...")
    clear_stop_flag()
    checkpoint = load_checkpoint()

    total_inserted = 0
    total_updated = 0

    for category in categories:
        logger.info(f"\n============================================================")
        logger.info(f"=== STARTING CATEGORY: {category} ===")
        logger.info(f"============================================================")
        
        for idx, district in enumerate(districts_to_scrape):
            # Check stop flag before starting next district/category
            if check_stop_flag():
                logger.info("Scraper execution stopped gracefully by user request.")
                return

            checkpoint_key = f"{category}::{district}"
            if checkpoint.get(checkpoint_key) == "done":
                logger.info(f"⏩ Skip: {district} for category '{category}' (already scraped).")
                continue

            logger.info(f"\n[{idx+1}/{len(districts_to_scrape)}] Scrapes {district} for '{category}'...")
            
            try:
                # Max 10 pages per district for high coverage
                inserted, updated = scrape_jwt_city(
                    district=district,
                    category=category,
                    pages=10,
                    limit=10,
                    dry_run=False,
                    subcategories=False,
                    use_proxy=(sys.platform != "win32")
                )
                
                total_inserted += inserted
                total_updated += updated
                
                # Mark as complete in checkpoint
                checkpoint[checkpoint_key] = "done"
                save_checkpoint(checkpoint)
                
                logger.info(f"✅ Success: {district} ({category}) -> New: {inserted} | Updated: {updated}")
                
                # Dynamic delay to prevent rate limits
                time.sleep(random.uniform(2.5, 5.0))
                
            except Exception as e:
                logger.error(f"❌ Error scraping {district} for category '{category}': {e}")
                time.sleep(5)

    logger.info(f"\n============================================================")
    logger.info(f"💊 Done! Total Inserted: {total_inserted} | Total Updated: {total_updated}")
    logger.info(f"============================================================")

if __name__ == "__main__":
    main()
