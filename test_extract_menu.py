
import sys
import os

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.scraper.desktop_scraper import extract_menu
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

test_url = "https://www.justdial.com/Ernakulam/Barbeque-Nation-Imperial-Trade-Centre-Near-Chennai-Silks-Arangath-Pullepady/0484PX484-X484-160322074653-U7T4_BZDET/menu"

print("Starting test of extract_menu()...")
driver = None
try:
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    print("Loading test URL...")
    driver.get(test_url)
    print("Waiting for page to load...")
    import time
    time.sleep(5)
    
    print("Calling extract_menu()...")
    menu_items = extract_menu(driver)
    
    print(f"\nSuccess! Found {len(menu_items)} menu items!")
    for i, item in enumerate(menu_items[:20], 1):
        print(f"{i}. {item['name']} - ₹{item['price']} (Veg: {item['is_veg']})")
        
    if len(menu_items) > 20:
        print(f"... and {len(menu_items)-20} more!")
        
    print("\nKeeping browser open for 30 seconds...")
    time.sleep(30)
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    print(traceback.format_exc())
finally:
    if driver:
        driver.quit()
