import undetected_chromedriver as uc
import time

url = "https://www.justdial.com/Thiruvananthapuram/Restaurants"
options = uc.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1280,720")

driver = uc.Chrome(options=options, use_subprocess=True)
try:
    driver.get(url)
    for _ in range(10):
        if 'nct-' in driver.current_url:
            break
        time.sleep(1)
    time.sleep(3)
    html = driver.page_source
    
    from app.api.categories import _extract_count_from_html
    count = _extract_count_from_html(html, "Restaurants", None)
    print("Final URL:", driver.current_url)
    print("Extracted Count:", count)
except Exception as e:
    print("Error:", e)
finally:
    try:
        driver.quit()
    except:
        pass
