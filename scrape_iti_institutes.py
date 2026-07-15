import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from jd_api_scraper import scrape_jwt_city

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

# ITI and vocational training related categories
categories = [
    "ITI Institutes",
    "Vocational Training Institutes",
    "Polytechnic Colleges",
    "Engineering Colleges",
    "Medical Colleges",
    "Arts And Science Colleges",
    "Law Colleges",
    "Nursing Colleges",
    "Management Institutes",
    "B.Ed Colleges",
    "Diploma Institutes",
    "Coaching Centres",
]

print(f"Starting batch scrape for {len(categories)} education categories in all {len(districts_to_scrape)} districts of Kerala.")

for category in categories:
    print(f"\n============================================================")
    print(f"=== STARTING CATEGORY: {category} ===")
    print(f"============================================================")
    for idx, district in enumerate(districts_to_scrape):
        print(f"\n--- [{idx+1}/{len(districts_to_scrape)}] Scrape '{category}' in {district} ---")
        try:
            scrape_jwt_city(
                district=district,
                category=category,
                pages=10,
                limit=10,
                dry_run=False,
                subcategories=False,
                use_proxy=(sys.platform != "win32")
            )
        except Exception as e:
            print(f"Error scraping {category} in {district}: {e}")

print("\nBatch scrape for all Education/ITI categories completed!")
