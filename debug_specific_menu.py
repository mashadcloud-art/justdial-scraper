
import sys
import os
import time
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

test_url = "https://www.justdial.com/Ernakulam/Barbeque-Nation-Imperial-Trade-Centre-Near-Chennai-Silks-Arangath-Pullepady/0484PX484-X484-160322074653-U7T4_BZDET/menu"

driver = None
try:
    print("Starting browser...")
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    print("Navigating to specific menu URL...")
    driver.get(test_url)
    print("Waiting for page to load fully (8 seconds)...")
    time.sleep(8)
    
    print("Saving page source to specific_menu_page.html...")
    with open("specific_menu_page.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
        
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    print("\n=== Looking for elements with 'menu' or 'item' in class ===")
    for el in soup.find_all(True):  # True finds all tags
        class_list = " ".join(el.get("class", []))
        text = el.get_text(strip=True)[:100]  # First 100 chars
        if "menu" in class_list.lower() or "item" in class_list.lower() or "₹" in text or "price" in class_list.lower():
            print(f"Tag: {el.name}, Classes: {class_list}, Text: {text}")
            
    # Also check for __NEXT_DATA__
    print("\n=== __NEXT_DATA__ script ===")
    next_data_script = soup.find("script", id="__NEXT_DATA__")
    if next_data_script and next_data_script.string:
        print("Found __NEXT_DATA__!")
        import json
        try:
            next_data = json.loads(next_data_script.string)
            results = next_data.get("props", {}).get("pageProps", {}).get("results", {}).get("results", {})
            print(f"  Results keys: {list(results.keys())[:30]}")  # First 30 keys
        except Exception as e:
            print(f"  Error parsing JSON: {e}")
    
    print("\n=== Keeping browser open for 60 seconds... ===")
    time.sleep(60)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    print(traceback.format_exc())
finally:
    if driver:
        driver.quit()
