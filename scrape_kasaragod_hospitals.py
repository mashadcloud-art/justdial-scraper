import sys
import os

# Ensure project path is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from adb_bulk_category_search import automate_category_search
import app.scraper.adb_location_search as adb_location_search

# List of major Kasaragod PIN Codes and Towns
KASARAGOD_LOCATIONS = [
    "671121 Kasaragod Town",
    "671122 Thalangara",
    "671123 Vidyanagar",
    "671314 Cherkala",
    "671315 Badiadka",
    "671321 Kanhangad",
    "671541 Nileshwar",
    "671531 Manjeshwar",
    "671313 Kumbla",
    "671316 Mulleria",
    "671328 Trikaripur",
    "Uppala Kasaragod",
    "Perla Kasaragod"
]

# Comprehensive list of Hospital categories
HOSPITAL_CATEGORIES = [
    "Hospitals",
    "Private Hospitals",
    "Government Hospitals",
    "Ayurvedic Hospitals",
    "Homeopathic Hospitals",
    "Maternity Hospitals",
    "Children Hospitals",
    "Dental Clinics",
    "Eye Hospitals",
    "Multispeciality Hospitals",
    "Clinics"
]

def main():
    print("======================================================")
    print("Starting Bulk Hospital Scraper for Kasaragod District")
    print("======================================================")
    
    # You can change the display ID if you are using a specific screen (like Samsung DeX)
    # adb_location_search.ADB_DISPLAY = 3 
    
    total_locations = len(KASARAGOD_LOCATIONS)
    
    for i, location in enumerate(KASARAGOD_LOCATIONS):
        print(f"\nProcessing Location {i+1}/{total_locations}: {location}")
        # Run the search automation for all hospital categories in this location
        # 10 scrolls per category is usually enough for a specific PIN code
        automate_category_search(location=location, categories=HOSPITAL_CATEGORIES, scrolls=10)
        
    print("\nALL KASARAGOD LOCATIONS COMPLETED!")

if __name__ == "__main__":
    main()
