import undetected_chromedriver as uc
import time

import os
current_dir = os.path.dirname(os.path.abspath(__file__))
chrome_drivers_dir = os.path.join(current_dir, "chrome_drivers")
os.makedirs(chrome_drivers_dir, exist_ok=True)

options = uc.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
try:
    driver = uc.Chrome(options=options, version_main=149, patcher_kwargs={"target_dir": chrome_drivers_dir})
except Exception as e:
    print("Failed with version_main=149:", e)
    print("Trying autodetect with patcher_kwargs...")
    driver = uc.Chrome(options=options, patcher_kwargs={"target_dir": chrome_drivers_dir})

try:
    print("Loading Kasaragod Fast Food...")
    driver.get("https://www.justdial.com/Kasaragod/Fast-Food")
    time.sleep(5)
    print("Current URL:", driver.current_url)
    
    # Check if page 2 works
    resolved_url = driver.current_url.split('?')[0].rstrip('/')
    page_2_url = f"{resolved_url}/page-2"
    print("Loading Page 2:", page_2_url)
    driver.get(page_2_url)
    print("Current URL after Page 2:", driver.current_url)
    print("PAGE SOURCE START:")
    print(driver.page_source[:500])
    print("PAGE SOURCE END")
    driver.save_screenshot("test_uc_screenshot.png")
finally:
    driver.quit()
