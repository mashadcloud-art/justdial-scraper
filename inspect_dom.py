from playwright.sync_api import sync_playwright
import codecs

def inspect_dom():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:8080/")
        page.wait_for_load_state("networkidle")
        
        # Dump the text content
        html = page.content()
        with codecs.open("dom_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        text = page.locator("body").inner_text()
        with codecs.open("dom_text.txt", "w", encoding="utf-8") as f:
            f.write(text)
            
        if "Emulator" in html or "Mobile" in html:
            print("YES! 'Emulator/Mobile' is present in the DOM HTML.")
        else:
            print("ERROR: 'Emulator/Mobile' is completely MISSING from the DOM HTML!")
            
        browser.close()

if __name__ == "__main__":
    inspect_dom()
