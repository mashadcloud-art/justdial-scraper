
import sys
import os
import time
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# Get the restaurant URL from our DB
test_url = "https://www.justdial.com/Ernakulam/Hotel-Woodlands-Sweets-Near-Vijaya-Bricks-Madakkathanam/0484PX484-X484-191112235026-Y3R2_BZDET"

driver = None
try:
    print("Starting browser...")
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    print("Navigating to test URL...")
    driver.get(test_url)
    print("Waiting for page load...")
    time.sleep(8)
    
    print("Saving page source to debug_page.html")
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
        
    print("=== Parsing page source to look for menu-related classes ===")
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    print("Finding all elements with 'menu' in class name or text:")
    for el in soup.find_all():
        class_str = " ".join(el.get("class", []))
        text_str = el.get_text(strip=True)[:50]
        if "menu" in class_str.lower() or "menu" in text_str.lower():
            print(f"Tag: {el.name}, Classes: {class_str}, Text: {text_str}")
            
    print("\nFinding all divs/spans that might be menu items:")
    all_elements = soup.find_all(["div", "span"])
    for el in all_elements:
        class_str = " ".join(el.get("class", []))
        if any(key in class_str for key in ["service", "catalogue", "item", "food"]):
            text = el.get_text(strip=True)
            if text and len(text) < 100:
                print(f"  Class: {class_str} → Text: {text}")
                
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    print(traceback.format_exc())
finally:
    if driver:
        print("\nKeeping browser open for 30s, then closing...")
        time.sleep(30)
        driver.quit()
    print("Done")

