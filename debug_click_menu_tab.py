
import sys
import os
import time
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

test_url = "https://www.justdial.com/Ernakulam/Hotel-Woodlands-Sweets-Near-Vijaya-Bricks-Madakkathanam/0484PX484-X484-191112235026-Y3R2_BZDET"

driver = None
try:
    print("Starting browser...")
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    print("Navigating to main URL...")
    driver.get(test_url)
    print("Waiting for page load...")
    time.sleep(8)
    
    # Find and click the Menu tab
    print("Looking for Menu tab...")
    menu_tab = None
    # Try different selectors for the Menu tab
    for selector in [
        "//div[contains(@class, 'jddetails_tabitem')]//span[contains(text(), 'Menu')]/..",
        "//span[contains(text(), 'Menu')]/ancestor::div[contains(@class, 'tabitem')]",
        "//span[contains(text(), 'Menu')]",
        "//div[contains(text(), 'Menu') and contains(@class, 'tab')]"
    ]:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            if elements:
                menu_tab = elements[0]
                print(f"Found Menu tab with selector: {selector}")
                break
        except Exception as e:
            continue
            
    if menu_tab:
        print("Clicking Menu tab...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", menu_tab)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", menu_tab)
        print("Waiting 8 seconds for Menu section to load...")
        time.sleep(8)
        
        # Now save the page source and look for menu items
        print("Saving page source after clicking Menu tab...")
        with open("debug_after_menu_click.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
            
        print("\n=== Now parsing page for menu items ===")
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Try to find any elements with price symbols
        for el in soup.find_all(["div", "span", "p"]):
            text = el.get_text(strip=True)
            if "₹" in text or "Rs" in text:
                classes = " ".join(el.get("class", []))
                # Get some context around the price
                parent = el.parent
                parent_text = parent.get_text(strip=True)[:150] if parent else ""
                print(f"\nFound price element: {text}")
                print(f"  Element classes: {classes}")
                print(f"  Parent context: {parent_text}")
                
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    print(traceback.format_exc())
finally:
    if driver:
        print("\nKeeping browser open for 40s, then closing...")
        time.sleep(40)
        driver.quit()
    print("Done")

