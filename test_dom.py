import time
import os
from playwright.sync_api import sync_playwright

json_data = """{
  "results": {
    "columns": ["docid", "name", "phone", "rating", "review_count", "address", "thumbnail", "latitude", "longitude"],
    "data": [
      ["12345", "Super Emulator Burger Joint", "+919876543210", "4.8", "120", "123 Test St, Ernakulam", "http://example.com/img1.jpg", "9.9", "76.2"],
      ["67890", "Mobile Magic Cafe", "+918765432109", "4.5", "85", "456 Mobile Ave, Kochi", "http://example.com/img2.jpg", "9.8", "76.3"]
    ]
  }
}"""

def get_screenshot():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        
        print("Loading dashboard...")
        page.goto("http://localhost:8080/")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        
        print("Selecting Mobile engine...")
        page.locator("select").first.select_option("emulator")
        time.sleep(1)
        
        print("Pasting JSON...")
        textarea = page.locator("textarea")
        textarea.fill(json_data)
        time.sleep(1)
        
        print("Clicking Ingest...")
        page.get_by_role("button", name="Ingest").click()
        time.sleep(3) # Wait for backend to process
        
        # Click on Listings Queue to see the new restaurants
        page.get_by_role("button", name="Listings Queue").click()
        time.sleep(2)
        
        # Click on "All States" dropdown and select "Kerala" (Wait, they might not have states populated, just let it load default)
        
        artifacts_dir = r"C:\Users\PC\.gemini\antigravity-ide\brain\24453cd6-c3a3-4090-90a5-4915528f709f"
        os.makedirs(artifacts_dir, exist_ok=True)
        path = os.path.join(artifacts_dir, "working_ui.png")
        
        print("Saving screenshot...")
        page.screenshot(path=path)
        browser.close()
        print("Done!")

if __name__ == "__main__":
    get_screenshot()
