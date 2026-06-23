import sys
import os

# Ensure project path is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from adb_bulk_category_search import automate_category_search
import app.scraper.adb_location_search as adb_location_search

# Just ONE location for testing
KASARAGOD_LOCATIONS = [
    "671121" # Kasaragod Town
]

# Just ONE category for testing
HOSPITAL_CATEGORIES = [
    "Hospitals"
]

def main():
    print("======================================================")
    print("Starting QUICK TEST Scraper")
    print("======================================================")
    
    # We will only do 3 scrolls for this quick test to see if it works
    for i, location in enumerate(KASARAGOD_LOCATIONS):
        print(f"\nProcessing Location: {location}")
        automate_category_search(location=location, categories=HOSPITAL_CATEGORIES, scrolls=3)
        
    print("\nQUICK TEST COMPLETED! Check your Dashboard to see the scraped data.")

if __name__ == "__main__":
    main()
