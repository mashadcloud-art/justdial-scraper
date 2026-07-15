import os
import sys
import time
import random
import logging

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from jd_api_scraper import scrape_jwt_city

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("kerala_hospitals_clinics_scraper")

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

# Playground, Sports Ground, Turf, and related categories
categories = [
    "Sports Ground",
    "Playgrounds",
    "Turf Grounds",
    "Football Turfs",
    "Cricket Grounds",
    "Indoor Stadiums",
    "Badminton Courts",
    "Mini Football Fields",
    "Stadiums"
]

logger.info("🏟️ Starting batch JustDial scrape for Kerala Playgrounds and Sports Grounds...")

for category in categories:
    logger.info(f"\n============================================================")
    logger.info(f"=== STARTING CATEGORY: {category} ===")
    logger.info(f"============================================================")
    
    for idx, district in enumerate(districts_to_scrape):
        logger.info(f"\n--- [{idx+1}/{len(districts_to_scrape)}] Scrape '{category}' in {district} ---")
        try:
            inserted, updated = scrape_jwt_city(
                district=district,
                category=category,
                pages=5,
                limit=10,
                dry_run=False,
                subcategories=False,
                use_proxy=(sys.platform != "win32")
            )
            logger.info(f"Result for {district} ({category}): {inserted} inserted, {updated} updated")
            time.sleep(random.uniform(2.0, 4.0))
        except Exception as e:
            logger.error(f"Error scraping {category} in {district}: {e}")
            time.sleep(3)

logger.info("\nBatch scrape completed!")
