from playwright.sync_api import sync_playwright
import time
import os

def take_screenshot():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        
        print("Navigating to dashboard...")
        page.goto("http://localhost:8080/")
        page.wait_for_load_state("networkidle")
        
        print("Selecting Emulator engine...")
        # Find the Engine dropdown and select "emulator"
        # The dropdown label is "Scraper Engine" for desktop and "Engine" for mobile. Let's look for "Scraper Engine"
        page.locator("text=Scraper Engine").locator("..").locator("select").select_option("emulator")
        
        time.sleep(1) # Wait for UI to update
        
        print("Taking screenshot...")
        # Save to the artifacts directory so the AI can embed it
        screenshot_path = r"C:\Users\PC\.gemini\antigravity-ide\brain\24453cd6-c3a3-4090-90a5-4915528f709f\emulator_ui.png"
        page.screenshot(path=screenshot_path)
        print(f"Saved screenshot to {screenshot_path}")
        
        browser.close()

if __name__ == "__main__":
    take_screenshot()
