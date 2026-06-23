import sys
import os

# Ensure project path is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scraper.desktop_scraper import scrape_city

if __name__ == "__main__":
    print("======================================================")
    print(" Starting Desktop Scraper (DOM) for Kasaragod Hospitals")
    print("======================================================")
    
    # Using the exact DOM scraper you asked for!
    # district = "Kasaragod"
    # main_cat = "Hospitals"
    # subcat = "All"
    scrape_city("Kasaragod", "Hospitals", "All", max_limit="All")
    
    print("\nFinished scraping using the DOM procedure!")
