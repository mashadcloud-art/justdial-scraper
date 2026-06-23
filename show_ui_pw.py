import os
import time
from playwright.sync_api import sync_playwright

def show_ui():
    with sync_playwright() as p:
        # Launch Chrome VISIBLY so the user sees it
        browser = p.chromium.launch(headless=False, channel="chrome")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        
        print("Opening dashboard...")
        page.goto("http://localhost:8080/")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        
        print("Clicking dropdown...")
        # In Playwright, we can click text
        dropdown = page.get_by_text("⚡ API (Fast)").first
        
        # Hover so user sees the mouse
        dropdown.hover()
        time.sleep(1)
        
        # Click to open dropdown
        dropdown.click()
        time.sleep(1)
        
        print("Selecting Emulator...")
        # Click the Mobile Emulator option
        mobile_option = page.get_by_text("📱 Mobile Emulator").first
        mobile_option.hover()
        time.sleep(1)
        mobile_option.click()
        
        time.sleep(1)
        
        # Now point out the JSON box
        print("Highlighting JSON box...")
        textarea = page.locator("textarea")
        textarea.hover()
        time.sleep(0.5)
        textarea.fill("--> PASTE YOUR HTTP TOOLKIT JSON RIGHT HERE <--")
        
        # Let the user look at it for 15 seconds
        time.sleep(15)
        
        browser.close()

if __name__ == "__main__":
    show_ui()
