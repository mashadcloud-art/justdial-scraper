import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scraper.desktop_scraper import scrape_city

if __name__ == "__main__":
    print("🚀 Starting scraper from scripts folder...")
    
    # 🟢 YOU CAN CHANGE THE CITY AND LIMIT HERE!
    # Example: Scrape 5 restaurants from Kochi
    scrape_city("Kochi", max_limit=5)