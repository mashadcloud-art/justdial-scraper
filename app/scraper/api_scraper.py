"""
Fast JustDial scraper — extracts data directly from search result pages.
Does NOT visit individual listing pages (which get blocked).
Uses the same undetected_chromedriver that successfully loads search pages.
"""
import json
import os
import re
import time
import requests
from typing import List, Dict, Set
from bs4 import BeautifulSoup
from app.scraper.logger import log

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

API_UPLOAD_URL = os.getenv("API_UPLOAD_URL", "http://localhost:8000/api/v1/upload-restaurant")
DEFAULT_WAIT = 20
SCROLL_PAUSE = 1.0


def build_driver(browser_type="chrome"):
    """Driver config that supports Chrome (with fallbacks) and Edge."""
    if browser_type == "edge":
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        from selenium import webdriver
        
        options = EdgeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=en-US")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        try:
            service = EdgeService(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)
        except Exception as e:
            log(f"⚠️ Failed to init Edge with EdgeChromiumDriverManager: {e}. Trying direct init...")
            return webdriver.Edge(options=options)

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=en-US")

    # Add persistent user data dir
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    chrome_user_data = os.path.join(project_root, "chrome_user_data")
    chrome_drivers_dir = os.path.join(project_root, "chrome_drivers")
    os.makedirs(chrome_user_data, exist_ok=True)
    os.makedirs(chrome_drivers_dir, exist_ok=True)
    options.add_argument(f"--user-data-dir={chrome_user_data}")

    try:
        return uc.Chrome(options=options, version_main=149, patcher_kwargs={"target_dir": chrome_drivers_dir})
    except Exception as e:
        log(f"⚠️ uc.Chrome version_main=149 failed: {e}. Trying autodetect...")
        try:
            opts2 = uc.ChromeOptions()
            opts2.add_argument("--start-maximized")
            opts2.add_argument(f"--user-data-dir={chrome_user_data}")
            return uc.Chrome(options=opts2, patcher_kwargs={"target_dir": chrome_drivers_dir})
        except Exception as e2:
            log(f"❌ uc.Chrome failed: {e2}. Falling back to standard Chrome...")
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            std_opts = ChromeOptions()
            std_opts.add_argument("--start-maximized")
            std_opts.add_argument(f"--user-data-dir={chrome_user_data}")
            return webdriver.Chrome(options=std_opts)


def wait_for_body(driver, timeout=DEFAULT_WAIT):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )


def safe_get(driver, url, timeout=DEFAULT_WAIT):
    driver.get(url)
    wait_for_body(driver, timeout)


def scroll_until_stable(driver, max_rounds=8, pause=SCROLL_PAUSE):
    last_height = driver.execute_script("return document.body.scrollHeight")
    stable_rounds = 0
    for _ in range(max_rounds):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            stable_rounds += 1
            if stable_rounds >= 2:
                break
        else:
            stable_rounds = 0
        last_height = new_height


def clean_phone(value: str) -> str:
    return re.sub(r"\D+", "", value or "").lstrip("91")


def extract_restaurants_from_search_page(driver) -> List[Dict]:
    """
    Extract ALL restaurant data directly from the search results page.
    This avoids visiting individual listing pages (which get blocked).
    """
    restaurants = []
    
    # First try: __NEXT_DATA__ JSON (has all data)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    next_script = soup.find("script", id="__NEXT_DATA__")
    
    if next_script and next_script.string:
        log("  Found __NEXT_DATA__ JSON! Extracting...")
        try:
            data = json.loads(next_script.string)
            restaurants = parse_next_data_search(data)
            if restaurants:
                log(f"  Extracted {len(restaurants)} restaurants from __NEXT_DATA__")
                return restaurants
        except Exception as e:
            log(f"  Error parsing __NEXT_DATA__: {e}", ok=False)
    
    # Second try: Extract from HTML DOM directly
    log("  Extracting from DOM elements...")
    restaurants = extract_from_dom(soup, driver)
    
    return restaurants


def parse_next_data_search(data: dict) -> List[Dict]:
    """Parse restaurant data from __NEXT_DATA__ on a search results page."""
    restaurants = []
    
    try:
        # Navigate to the results data
        page_props = data.get("props", {}).get("pageProps", {})
        
        # Try new layout listData.results first, then fallback to results
        results = page_props.get("listData", {}).get("results", {})
        if not results or not isinstance(results, dict) or "data" not in results:
            results = page_props.get("results", {})
            
        result_data = results.get("results", {}) if isinstance(results, dict) and "results" in results else results
        
        if isinstance(result_data, dict):
            # Check if it has 'columns' and 'data' (API format)
            if "columns" in result_data and "data" in result_data:
                columns = result_data["columns"]
                rows = result_data["data"]
                log(f"  Found API format: {len(columns)} columns, {len(rows)} rows")
                
                col_map = {col: i for i, col in enumerate(columns)}
                
                for row in rows:
                    if not isinstance(row, list):
                        continue
                    r = parse_api_row(row, col_map)
                    if r:
                        restaurants.append(r)
                return restaurants
            
            # Single result page format
            if "name" in result_data:
                restaurants.append({
                    "name": result_data.get("name", ""),
                    "phone": clean_phone(result_data.get("VNumber", "")),
                    "address": result_data.get("address", result_data.get("NewAddress", "")),
                    "rating": str(result_data.get("compRating", "")),
                    "category": result_data.get("type", ""),
                    "images": [],
                    "source_url": "",
                })
                return restaurants
        
        # Try direct 'results' as list
        if isinstance(result_data, list):
            for item in result_data:
                if isinstance(item, dict) and "name" in item:
                    restaurants.append({
                        "name": item.get("name", ""),
                        "phone": clean_phone(item.get("VNumber", item.get("phone", ""))),
                        "address": item.get("address", item.get("NewAddress", "")),
                        "rating": str(item.get("compRating", item.get("rating", ""))),
                        "category": item.get("type", item.get("category", "")),
                        "images": [],
                        "source_url": "",
                    })
        
        # Try looking deeper - sometimes results are nested
        if not restaurants:
            # Search recursively for arrays with restaurant-like objects
            restaurants = search_for_restaurants(page_props)
            
    except Exception as e:
        log(f"  Error in parse_next_data_search: {e}", ok=False)
    
    return restaurants


def search_for_restaurants(data, depth=0) -> List[Dict]:
    """Recursively search for restaurant data in nested JSON."""
    if depth > 6:
        return []
    
    results = []
    
    if isinstance(data, dict):
        # Check for columns+data format
        if "columns" in data and "data" in data:
            columns = data["columns"]
            rows = data["data"]
            if isinstance(rows, list) and rows:
                col_map = {col: i for i, col in enumerate(columns)}
                for row in rows:
                    if isinstance(row, list):
                        r = parse_api_row(row, col_map)
                        if r:
                            results.append(r)
                if results:
                    return results
        
        for key, val in data.items():
            found = search_for_restaurants(val, depth + 1)
            if found:
                return found
    
    elif isinstance(data, list) and data:
        # Check if this is a list of restaurant-like dicts
        if isinstance(data[0], dict) and "name" in data[0]:
            for item in data:
                if isinstance(item, dict) and item.get("name"):
                    results.append({
                        "name": item.get("name", ""),
                        "phone": clean_phone(str(item.get("VNumber", item.get("phone", "")))),
                        "address": item.get("address", item.get("NewAddress", "")),
                        "rating": str(item.get("compRating", item.get("rating", ""))),
                        "category": item.get("type", ""),
                        "images": [],
                        "source_url": "",
                    })
            if results:
                return results
        
        for item in data[:20]:
            found = search_for_restaurants(item, depth + 1)
            if found:
                results.extend(found)
        if results:
            return results
    
    return results


def parse_api_row(row: list, col_map: dict) -> Dict:
    """Parse a single row from JustDial's column/data API format."""
    def get(key, default=""):
        idx = col_map.get(key)
        if idx is not None and idx < len(row):
            val = row[idx]
            return val if val is not None else default
        return default
    
    name = get("name", "")
    if not name:
        return None
    
    # Phone from 'an' field
    phone = ""
    an = get("an")
    if isinstance(an, dict):
        mobile = an.get("m", "")
        if mobile:
            phone = re.sub(r"[^\d]", "", str(mobile).split(",")[0])
            if phone.startswith("91") and len(phone) > 10:
                phone = phone[2:]
    if not phone:
        phone = clean_phone(str(get("VNumber", "")))
    
    address = get("NewAddress", get("area", ""))
    city = get("city", "")
    
    # Images
    images = []
    dimages = get("dimages")
    if isinstance(dimages, list):
        images = [u for u in dimages if isinstance(u, str) and u.startswith("http")][:10]
    
    thumbnail = get("thumbnail", "")
    if thumbnail and thumbnail.startswith("http") and thumbnail not in images:
        images.insert(0, thumbnail)
    
    opening_hours = ""
    opstring = get("opstring")
    if isinstance(opstring, dict):
        opening_hours = opstring.get("timing", "")

    weburl = get("weburl", "")
    source_url = f"https://www.justdial.com/{weburl}" if weburl else ""

    return {
        "name": name,
        "phone": phone,
        "address": f"{address}, {city}" if city and address else (address or city),
        "rating": str(get("compRating", "")),
        "total_reviews": str(get("totalReviews", "")),
        "category": get("type", ""),
        "images": images,
        "source_url": source_url,
        "docid": get("docid", ""),
        "latitude": str(get("lat", get("latitude", ""))),
        "longitude": str(get("lon", get("longitude", ""))),
        "opening_hours": opening_hours,
    }


def extract_from_dom(soup: BeautifulSoup, driver) -> List[Dict]:
    """Extract restaurant data from the page DOM / HTML elements."""
    restaurants = []
    
    # JustDial uses <a> tags with _BZDET in href for listing links
    # The name is in the URL and nearby text
    bzdet_links = soup.find_all("a", href=re.compile(r"_BZDET"))
    
    if bzdet_links:
        log(f"  Found {len(bzdet_links)} listing links (_BZDET)")
        
        seen_urls: Set[str] = set()
        for link in bzdet_links:
            href = link.get("href", "")
            if not href.startswith("http"):
                href = f"https://www.justdial.com{href}"
            href = href.split("?")[0].rstrip("/")
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            # Get the name from link text or parent element
            name = link.get_text(strip=True)
            
            # If no text in the link itself, try finding nearby name elements
            if not name or len(name) < 2:
                parent = link.find_parent("li") or link.find_parent("div")
                if parent:
                    name_el = parent.find(class_=re.compile(r"lng_cont_name|jcn|store.name"))
                    if name_el:
                        name = name_el.get_text(strip=True)
            
            # Extract name from the URL as fallback
            if not name or len(name) < 2:
                url_parts = href.split("/")
                for part in url_parts:
                    if "_BZDET" in part:
                        name = part.split("_BZDET")[0].split("-")
                        # Remove the encoded ID at the end
                        name = [p for p in name if not re.match(r"^[A-Z0-9]{8,}$", p)]
                        name = " ".join(name).replace("-", " ").title()
                        break
            
            if not name or len(name) < 2:
                continue
            
            # Try to find phone, address, rating from parent container
            phone = ""
            address = ""
            rating = ""
            category = ""
            
            parent = link.find_parent("li") or link.find_parent("div", class_=re.compile(r"cntanr|resultbox|store"))
            if parent:
                # Address
                addr_el = parent.find(class_=re.compile(r"cont_sw_addr|dn_addr|address"))
                if addr_el:
                    address = addr_el.get_text(strip=True)
                
                # Rating
                rating_el = parent.find(class_=re.compile(r"green.box|star|rating"))
                if rating_el:
                    match = re.search(r"[\d.]+", rating_el.get_text(strip=True))
                    if match:
                        rating = match.group()
                
                # Category
                cat_el = parent.find(class_=re.compile(r"cont_cat|category"))
                if cat_el:
                    category = cat_el.get_text(strip=True)
                
                # Phone
                phone_el = parent.find("a", href=re.compile(r"^tel:"))
                if phone_el:
                    phone = re.sub(r"[^\d]", "", phone_el["href"].replace("tel:", ""))
            
            restaurants.append({
                "name": name,
                "phone": phone,
                "address": address,
                "rating": rating,
                "category": category,
                "images": [],
                "source_url": href,
            })
    
    # Also try direct element selectors
    if not restaurants:
        name_elements = soup.select(".lng_cont_name, .jcn, .store-name")
        log(f"  Found {len(name_elements)} name elements via CSS selectors")
        
        for el in name_elements:
            name = el.get_text(strip=True)
            if name and len(name) > 1:
                # Find the parent link for the source URL
                parent_link = el.find_parent("a")
                source_url = ""
                if parent_link:
                    source_url = parent_link.get("href", "")
                    if source_url and not source_url.startswith("http"):
                        source_url = f"https://www.justdial.com{source_url}"
                
                restaurants.append({
                    "name": name,
                    "phone": "",
                    "address": "",
                    "rating": "",
                    "category": "",
                    "images": [],
                    "source_url": source_url,
                })
    
    return restaurants


def upload_to_api(restaurant: Dict, district: str) -> bool:
    """Upload a parsed restaurant to our local API."""
    source_url = restaurant.get("source_url", "")
    if not source_url:
        source_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{restaurant['name'].replace(' ', '-')}"
    
    data = {
        "name": restaurant["name"],
        "phone": restaurant.get("phone", ""),
        "address": restaurant.get("address", ""),
        "source_url": source_url,
        "category": restaurant.get("category", ""),
        "opening_hours": "",
        "district": district,
    }

    images = restaurant.get("images", [])
    if images:
        image_urls = [{"path": url, "category": "general"} for url in images[:20]]
        data["image_urls_json"] = json.dumps(image_urls)

    try:
        resp = requests.post(API_UPLOAD_URL, data=data, timeout=15)
        return resp.status_code in (200, 201)
    except Exception as e:
        log(f"   Upload error: {e}", ok=False)
        return False


def scrape_city(district: str, main_cat: str, subcat: str, max_limit=10, fast_mode=False, start_page=1, browser_type="chrome"):
    """
    Fast scraper: extracts restaurant data directly from search result pages.
    Does NOT visit individual listing pages (which JustDial blocks).
    """
    category = subcat if (subcat and subcat != "All" and subcat.strip()) else main_cat
    
    base_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{category.replace(' ', '-')}"
    
    log(f"Fast Engine ({browser_type}) Starting - {district} / {category}")
    log(f"Max entries: {max_limit}, start page: {start_page}")

    max_count = float('inf') if max_limit == "All" else int(max_limit)
    scraped_count = 0

    driver = None
    try:
        log(f"Launching {browser_type} driver...")
        driver = build_driver(browser_type=browser_type)
        
        # Resolve canonical URL
        log(f"Loading: {base_url}")
        safe_get(driver, base_url)
        
        resolved_base_url = base_url
        for _ in range(15):
            if 'nct-' in driver.current_url:
                resolved_base_url = driver.current_url.split('?')[0].rstrip('/')
                break
            time.sleep(1)
        
        log(f"Resolved URL: {resolved_base_url}")
        
        page_num = start_page
        while scraped_count < max_count:
            current_url = resolved_base_url if page_num == 1 else f"{resolved_base_url}/page-{page_num}"
            
            if page_num > 1:
                log(f"Loading page {page_num}: {current_url}")
                safe_get(driver, current_url)
            
            # Scroll to load all lazy content
            scroll_until_stable(driver, max_rounds=6)
            
            # Extract ALL restaurant data from this search page
            log(f"Extracting data from page {page_num}...")
            restaurants = extract_restaurants_from_search_page(driver)
            
            if not restaurants:
                log(f"No restaurants found on page {page_num}. Reached end of results.")
                break
            
            log(f"Found {len(restaurants)} restaurants on page {page_num}!")
            
            for restaurant in restaurants:
                if scraped_count >= max_count:
                    break
                
                name = restaurant.get("name", "Unknown")
                if not name or name == "Unknown" or len(name) < 2:
                    continue
                
                scraped_count += 1
                phone = restaurant.get("phone", "")
                addr = restaurant.get("address", "")
                rating = restaurant.get("rating", "")
                img_count = len(restaurant.get("images", []))
                
                log(f"  [{scraped_count}/{max_count}] {name}")
                if phone:
                    log(f"    Phone: {phone}")
                if addr:
                    log(f"    Address: {addr}")
                if rating:
                    log(f"    Rating: {rating} | Images: {img_count}")
                
                if upload_to_api(restaurant, district):
                    log(f"    Uploaded!")
                else:
                    log(f"    Upload failed.", ok=False)
            
            page_num += 1
            time.sleep(1)  # Brief pause between pages
                
    except Exception as e:
        log(f"Fatal error: {e}", ok=False)
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        log(f"\nFast Engine Finished. Scraped {scraped_count} restaurants total.")
