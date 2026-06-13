
import sys
import os
import time
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# Get the restaurant URL from our DB, then append /menu
test_url = "https://www.justdial.com/Ernakulam/Hotel-Woodlands-Sweets-Near-Vijaya-Bricks-Madakkathanam/0484PX484-X484-191112235026-Y3R2_BZDET/menu"

driver = None
try:
    print("Starting browser...")
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    print("Navigating to test menu URL...")
    driver.get(test_url)
    print("Waiting for page load...")
    time.sleep(10)
    
    print("Saving menu page source to debug_menu_page.html")
    with open("debug_menu_page.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
        
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    print("Looking for any menu-related elements:")
    for el in soup.find_all(["div", "span", "h2", "h3", "li"]):
        text = el.get_text(strip=True)
        classes = " ".join(el.get("class", []))
        if any(key in text.lower() or key in classes.lower() for key in ["menu", "food", "item", "price", "₹", "rs"]):
            if 3 < len(text) < 200:
                print(f"{el.name} ({classes}): {text}")
                
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

