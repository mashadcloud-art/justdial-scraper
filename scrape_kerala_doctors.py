import os
import sys
import time
import random
import logging

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from jd_api_scraper import scrape_jwt_city

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("kerala_doctors_scraper")

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

# Comprehensive medical specialist categories to scrape
categories = [
    "Doctors",
    "General Physician Doctors",
    "Clinics",
    "Dentists",
    "Gynecologist & Obstetrician Doctors",
    "Pediatricians",
    "Dermatologists",
    "Orthopaedic Doctors",
    "Cardiologists",
    "Ophthalmologists",
    "ENT Doctors",
    "Ayurvedic Doctors",
    "Homeopathic Doctors"
]

logger.info("🩺 Starting batch JustDial scrape for all Kerala Doctors and Medical Specialists...")
logger.info(f"Targeting {len(categories)} categories across all {len(districts_to_scrape)} districts.")

for category in categories:
    logger.info(f"\n============================================================")
    logger.info(f"=== STARTING CATEGORY: {category} ===")
    logger.info(f"============================================================")
    
    for idx, district in enumerate(districts_to_scrape):
        logger.info(f"\n--- [{idx+1}/{len(districts_to_scrape)}] Scrape '{category}' in {district} ---")
        try:
            # We scrape pages=8 (enough to pull unique listings since it targets every pincode in the district)
            inserted, updated = scrape_jwt_city(
                district=district,
                category=category,
                pages=8,
                limit=10,
                dry_run=False,
                subcategories=False,
                use_proxy=True  # Enables proxying if you have a proxy config
            )
            logger.info(f"Result for {district} ({category}): {inserted} inserted, {updated} updated")
            time.sleep(random.uniform(2.0, 5.0))
        except Exception as e:
            logger.error(f"Error scraping {category} in {district}: {e}")
            time.sleep(3)

logger.info("\n🩺 Batch doctors scrape completed!")
