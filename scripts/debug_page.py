import time
from selenium import webdriver

# Open a specific restaurant page and save the HTML
RESTAURANT_URL = "https://www.justdial.com/Mumbai/Mao-Family-Restaurant-Near-Theatre-Kalbadevi/022PXX22-XX22-140804130028-J6U9_BZDET"

print("🔍 Opening restaurant page for debugging...")

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

try:
    driver.get(RESTAURANT_URL)
    time.sleep(5)
    
    # Scroll to load content
    print("📜 Scrolling...")
    for _ in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
    
    # Save the HTML
    html = driver.page_source
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print("✅ HTML saved to debug_page.html")
    print("📂 Open this file in your browser to see what's on the page")
    
    input("Press Enter to close...")
    
finally:
    driver.quit()