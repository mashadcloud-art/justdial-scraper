import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scraper.desktop_scraper import scrape_city

if __name__ == "__main__":
    print("Starting Desktop Scraper (DOM) for 10 restaurants...")
    scrape_city("Kasaragod", "Restaurants", "All", max_limit=10)
    print("Finished.")
