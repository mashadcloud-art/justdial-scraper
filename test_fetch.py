import sys
import time
import json
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from app.api.categories import _extract_count_from_html

def test_url(url, cat):
    print(f"Fetching: {url}")
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options, use_subprocess=True)
    
    try:
        driver.get(url)
        time.sleep(5)
        print("Final URL after redirect:", driver.current_url)
        html = driver.page_source
        count = _extract_count_from_html(html, cat, None)
        print(f"Count: {count}")
    finally:
        driver.quit()

if __name__ == '__main__':
    test_url("https://www.justdial.com/Thiruvananthapuram/Restaurants", "Restaurants")
