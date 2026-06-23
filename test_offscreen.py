import undetected_chromedriver as uc
import time

url = "https://www.justdial.com/Thiruvananthapuram/Restaurants"
print("Trying off-screen Chrome...")

options = uc.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
# The magic trick: place window off-screen so user doesn't see it
options.add_argument("--window-position=-32000,-32000")
options.add_argument("--window-size=1280,720")

driver = uc.Chrome(options=options, use_subprocess=True)
try:
    driver.get(url)
    
    # Wait for redirect
    for _ in range(10):
        if 'nct-' in driver.current_url:
            break
        time.sleep(1)
        
    time.sleep(3)
    
    from app.api.categories import _extract_count_from_html
    count = _extract_count_from_html(driver.page_source, "Restaurants", None)
    print("Magic! Count:", count)
except Exception as e:
    print("Error:", e)
finally:
    driver.quit()
