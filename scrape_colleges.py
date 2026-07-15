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
logger = logging.getLogger("colleges_scraper")

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

# All college-related categories
categories = [
    "Colleges",
    "Engineering Colleges",
    "Medical Colleges",
    "Nursing Colleges",
    "B.Ed Colleges",
    "Law Colleges",
    "Arts & Science Colleges",
    "Polytechnic Colleges",
    "Diploma Institutes"
]

CHECKPOINT_FILE = os.path.join("data", "scrape_checkpoint_colleges_main.json")
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
    logger.info("🎓 Starting Colleges Scraper...")
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

            key = f"{district.lower()}|{category.lower()}"
            if checkpoint.get(key) == "done":
                logger.info(f"✅ [CHECKPOINT] Already completed '{category}' in {district}. Skipping.")
                continue

            logger.info(f"\n--- [{idx+1}/{len(districts_to_scrape)}] Scrape '{category}' in {district} ---")
            try:
                # Run the scraper
                ins, upd = scrape_jwt_city(
                    district=district,
                    category=category,
                    pages=10,
                    limit=10,
                    dry_run=False,
                    subcategories=False,
                    use_proxy=(sys.platform != "win32")  # Enable proxy on Linux cloud VPS
                )
                
                total_inserted += ins
                total_updated += upd
                
                # Mark category+district as completed
                checkpoint[key] = "done"
                save_checkpoint(checkpoint)
                logger.info(f"💾 Saved progress: '{category}' in {district} marked as done.")
                
            except Exception as e:
                logger.error(f"❌ Error scraping {category} in {district}: {e}")
                # Wait before next iteration if there is an error
                time.sleep(5)

            # Polite delay between runs
            time.sleep(random.uniform(2.0, 5.0))

    logger.info(f"Batch scrape for Colleges completed! Total inserted: {total_inserted}")

if __name__ == "__main__":
    main()
