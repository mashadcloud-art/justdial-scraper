import time
from playwright.sync_api import sync_playwright

def get_screenshot():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        
        page.goto("http://localhost:8080/")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        
        # Click the Engine dropdown 
        page.get_by_text("⚡ API").first.click()
        time.sleep(1)
        
        # Select the Mobile Emulator
        page.get_by_text("📱 Mobile").first.click()
        time.sleep(1)
        
        # Type into the JSON area
        page.locator("textarea").fill("--> THIS IS WHERE YOU PASTE THE JSON <--")
        
        # Take a screenshot
        path = r"C:\Users\PC\.gemini\antigravity-ide\brain\24453cd6-c3a3-4090-90a5-4915528f709f\final_ui.png"
        page.screenshot(path=path)
        browser.close()

if __name__ == "__main__":
    get_screenshot()
