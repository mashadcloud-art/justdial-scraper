import undetected_chromedriver as uc
import time

print("1. Configuring options...")
options = uc.ChromeOptions()

print("2. Attempting to launch the browser...")
try:
    driver = uc.Chrome(options=options)
    print("3. Browser launched successfully! Navigating to Google...")
    driver.get("https://www.google.com")
    time.sleep(3)
    driver.quit()
    print("✅ TEST PASSED. The core driver works.")
except Exception as e:
    print(f"❌ TEST FAILED. Error: {e}")