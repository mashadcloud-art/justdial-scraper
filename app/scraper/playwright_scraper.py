from app.scraper.logger import log
import json
import logging
import time
import requests
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth

logger = logging.getLogger(__name__)

API_UPLOAD_URL = "http://localhost:8000/api/v1/upload-listing"

def _extract_from_dom(page_source):
    from bs4 import BeautifulSoup
    import re
    soup = BeautifulSoup(page_source, 'html.parser')
    
    extracted = []
    seen_names = set()
    
    # Find all business name links containing _BZDET
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if "_BZDET" not in href:
            continue
        text = a_tag.get_text(strip=True)
        # Skip "+135More" or similar helper links
        if not text or text.startswith("+") or "more" in text.lower():
            continue
            
        name = text.strip()
        if name not in seen_names:
            seen_names.add(name)
            
            # Look for contact details in parent/sibling elements
            phone = "N/A"
            parent = a_tag.find_parent()
            if parent:
                # Search parent or sibling structures for phone number patterns
                parent_text = parent.get_text()
                phone_match = re.search(r'(?:\+91|0)?[6-9]\d{9}', parent_text)
                if phone_match:
                    phone = phone_match.group(0)
            
            extracted.append({"name": name, "phone": phone})
            
    log(f"[DEBUG] _extract_from_dom extracted {len(extracted)} items.")
    return extracted

def scrape_city(district: str, main_cat: str, subcat: str, max_limit=10, fast_mode=False, start_page=1, browser_type="chrome"):
    base_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{subcat.replace(' ', '-')}"
    if subcat == "All" or not subcat.strip():
        base_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{main_cat.replace(' ', '-')}"
        
    log(f"Playwright Engine ({browser_type}) Starting Scrape: {base_url}")
    
    scraped_count = 0
    max_count = float('inf') if max_limit == "All" else int(max_limit)
    
    try:
        with sync_playwright() as p:
            import sys
            is_linux = sys.platform.startswith('linux')
            headless_mode = is_linux or os.getenv("HEADLESS", "false").lower() == "true"
            launch_args = {"headless": headless_mode}
            if browser_type == "edge":
                launch_args["channel"] = "msedge"
            browser = p.chromium.launch(**launch_args)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            
            # First resolve the canonical URL by loading page 1
            log(f"Resolving canonical URL for {base_url}...")
            page.goto(base_url, timeout=60000)
            resolved_base_url = base_url
            for _ in range(15):
                if 'nct-' in page.url:
                    resolved_base_url = page.url.split('?')[0].rstrip('/')
                    break
                time.sleep(1)
                
            log(f"Resolved canonical URL: {resolved_base_url}")
            
            max_pages = 50 if max_limit == "All" else (max_count // 10) + 1
            
            for page_num in range(start_page, start_page + max_pages):
                if scraped_count >= max_count:
                    break
                    
                log(f"Fetching page {page_num}...")
                if page_num == 1 and start_page == 1:
                    # We already loaded page 1 to resolve the URL, no need to reload
                    pass 
                else:
                    url = f"{resolved_base_url}/page-{page_num}"
                    page.goto(url, timeout=60000)
                
                time.sleep(7)  # Wait for JS render
                
                # Try to click "Show Number" buttons to decode numbers if they exist
                try:
                    page.evaluate('''() => {
                        let buttons = document.querySelectorAll('span, div, button, a');
                        for (let b of buttons) {
                            if (b.innerText && b.innerText.toLowerCase().includes('show number')) {
                                b.click();
                            }
                        }
                    }''')
                    time.sleep(2) # wait for decoding
                except Exception:
                    pass
                    
                items = _extract_from_dom(page.content())
                
                if not items:
                    log("No items found on this page, might have reached the end.")
                    break
                    
                for item in items:
                    if scraped_count >= max_count:
                        break
                        
                    name = item['name']
                    phone = item['phone']
                    
                    # Push to database synchronously
                    payload = {
                        'name': name,
                        'phone': phone,
                        'address': f"{district}",  # Simplified for now
                        'source_url': page.url,
                        'category': subcat,
                        'district': district
                    }
                    try:
                        requests.post(API_UPLOAD_URL, data=payload, timeout=10)
                        log(f"✅ Uploaded: {name} ({phone})")
                        scraped_count += 1
                    except Exception as e:
                        log(f"❌ Upload failed for {name}: {e}")
                        
            browser.close()
    except Exception as e:
        log(f"Error during Playwright scrape: {e}")
                
    log(f"Playwright Engine Finished. Scraped {scraped_count} listings.")

def preview_page(district: str, main_cat: str, subcat: str, page_num=1, browser_type="chrome"):
    base_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{subcat.replace(' ', '-')}"
    if subcat == "All" or not subcat.strip():
        base_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{main_cat.replace(' ', '-')}"
        
    results = []
    
    try:
        with sync_playwright() as p:
            import sys
            is_linux = sys.platform.startswith('linux')
            headless_mode = is_linux or os.getenv("HEADLESS", "false").lower() == "true"
            launch_args = {"headless": headless_mode}
            if browser_type == "edge":
                launch_args["channel"] = "msedge"
            browser = p.chromium.launch(**launch_args)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            
            # First resolve the canonical URL by loading page 1
            log(f"[DEBUG] Resolving canonical URL for {base_url}...")
            page.goto(base_url, timeout=60000)
            resolved_base_url = base_url
            for _ in range(15):
                if 'nct-' in page.url:
                    resolved_base_url = page.url.split('?')[0].rstrip('/')
                    break
                time.sleep(1)
                
            log(f"[DEBUG] Resolved canonical URL: {resolved_base_url}")
            
            if page_num > 1:
                url = f"{resolved_base_url}/page-{page_num}"
                log(f"[DEBUG] preview_page loading {url}")
                page.goto(url, timeout=60000)
                time.sleep(7)  # Wait for JS render
            else:
                log(f"[DEBUG] preview_page using already loaded page 1")
                time.sleep(7)  # Wait for JS render
            
            results = _extract_from_dom(page.content())
            browser.close()
    except Exception as e:
        log(f"Error during Playwright preview: {e}")
                
    return results
