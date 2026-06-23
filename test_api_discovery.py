"""Test: Connect to Chrome with user's existing profile (cookies/session)."""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import os

# Use the user's actual Chrome profile to bypass JustDial detection
user_data_dir = os.path.expanduser("~") + r"\AppData\Local\Google\Chrome\User Data"
print(f"Chrome profile dir: {user_data_dir}")
print(f"Exists: {os.path.exists(user_data_dir)}")

print("Launching Chrome with user profile...")
options = uc.ChromeOptions()
options.add_argument(f"--user-data-dir={user_data_dir}")
options.add_argument("--profile-directory=Default")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1280,900")

try:
    driver = uc.Chrome(options=options, version_main=149)
    
    url = "https://www.justdial.com/Ernakulam/Restaurants"
    print(f"Loading: {url}")
    driver.get(url)
    time.sleep(8)
    
    print(f"Title: {driver.title}")
    print(f"URL: {driver.current_url}")
    page_size = len(driver.page_source)
    print(f"Page source size: {page_size} bytes")
    
    if page_size > 100:
        # Scroll
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        
        # Find names
        for sel in [".lng_cont_name", ".jcn", ".store-name a", "a.lng_cont_name"]:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                names = [e.text.strip() for e in els[:10] if e.text.strip()]
                print(f"\n{sel}: {len(els)} found. Names: {names}")
        
        print(f"\nFirst 1000 chars of page:\n{driver.page_source[:1000]}")
    else:
        print("Empty page - still blocked!")
        print(f"Source: {driver.page_source}")
    
    driver.quit()

except Exception as e:
    print(f"Error: {e}")
    # If Chrome is already running, try remote debugging
    print("\nTrying remote debugging approach...")
    print("You may need to close all Chrome windows first.")
