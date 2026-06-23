import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scraper.desktop_scraper import scrape_single_url

test_url = "https://www.justdial.com/Kasaragod/Bungalow-47-Opp-Chithari-Juma-Masjid-Kanhangad/9999P4994-4994-180531160712-S2E3_BZDET"

print("Starting test scrape of Jithu Joji...")
success = scrape_single_url(test_url)
print(f"Scrape completed. Success: {success}")
