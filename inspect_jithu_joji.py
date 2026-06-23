import sys
import os
import time
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

test_url = "https://www.justdial.com/Thiruvananthapuram/Jithu-Joji-Fast-Food-Poojappura/0471PX471-X471-140604102004-Z1W3_BZDET"

driver = None
try:
    print("Starting browser...")
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1200,800")
    # Use user data dir to reuse login/cookies/profile if needed
    project_root = os.path.abspath(os.path.dirname(__file__))
    user_data_dir = os.path.join(project_root, "chrome_user_data")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    
    driver = uc.Chrome(options=options)
    
    print("Navigating to URL...")
    driver.get(test_url)
    
    print("Waiting for page load (8 seconds)... Please solve CAPTCHA if any!")
    time.sleep(8)
    
    # Save base page
    with open("jithu_joji_base.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("Base page source saved.")
    
    # Look for Menu tab and click it
    menu_tab = None
    for selector in [
        "//div[contains(@class, 'jddetails_tabitem')]//span[contains(text(), 'Menu')]/..",
        "//span[contains(text(), 'Menu')]/ancestor::div[contains(@class, 'tabitem')]",
        "//span[contains(text(), 'Menu')]",
        "//div[contains(text(), 'Menu') and contains(@class, 'tab')]"
    ]:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            if elements:
                for el in elements:
                    if el.is_displayed():
                        menu_tab = el
                        print(f"Found visible Menu tab with selector: {selector}")
                        break
                if menu_tab:
                    break
        except Exception:
            continue
            
    if menu_tab:
        print("Clicking Menu tab...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", menu_tab)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", menu_tab)
        print("Clicked Menu tab. Waiting for menu to load (6 seconds)...")
        time.sleep(6)
        
        with open("jithu_joji_menu_clicked.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Menu page source saved.")
    else:
        print("Menu tab NOT found or NOT visible.")

    # Now navigate to the gallery page to see where similar businesses are
    clean_url = test_url.split('?')[0].rstrip('/')
    gallery_url = f"{clean_url}/gallery?type=all"
    print(f"Navigating to Gallery URL: {gallery_url}")
    driver.get(gallery_url)
    time.sleep(6)
    
    with open("jithu_joji_gallery.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("Gallery page source saved.")
    
    print("Done gathering pages.")

except Exception as e:
    print("Error during inspection:", e)
finally:
    if driver:
        driver.quit()
