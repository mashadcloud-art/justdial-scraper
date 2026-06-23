from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
import time

def run():
    with sync_playwright() as p:
        user_data_dir = r"C:\Users\PC\Documents\trae_projects\Scapre for thozil\scraper_chrome_profile"
        executable_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        import os
        if not os.path.exists(executable_path):
            executable_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=executable_path,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        stealth_sync(page)
        
        print("Navigating to JustDial Kasaragod Fast Food...")
        page.goto("https://www.justdial.com/Kasaragod/Fast-Food", timeout=60000)
        time.sleep(5)
        
        print("Page URL:", page.url)
        print("Page Title:", page.title())
        content = page.content()
        print("Length of content:", len(content))
        print("First 200 chars:")
        print(content[:200])
        
        context.close()

if __name__ == "__main__":
    run()
