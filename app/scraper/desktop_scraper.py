import os
import time
import json
import re
import requests
import shutil
import tempfile
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# GLOBAL STOP FLAG - for instant stop!
# ==========================================
SHOULD_STOP = False
CURRENT_DRIVER = None
# ==========================================

# Configure undetected_chromedriver to use project directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
driver_dir = os.path.join(project_root, "chrome_drivers")
user_data_dir = os.path.join(project_root, "chrome_user_data")
os.makedirs(driver_dir, exist_ok=True)
os.makedirs(user_data_dir, exist_ok=True)

# ==========================================
# CONFIGURATION
# ==========================================
API_UPLOAD_URL = "http://localhost:8000/api/v1/upload-restaurant"
LOCAL_IMAGE_FOLDER = "./scraped_images"

KERALA_CITIES = [
    "Kochi", "Thiruvananthapuram", "Kozhikode", "Thrissur", "Kollam",
    "Kannur", "Palakkad", "Alappuzha", "Kottayam", "Malappuram",
    "Thiruvalla", "Pathanamthitta"
]

os.makedirs(LOCAL_IMAGE_FOLDER, exist_ok=True)

# ==========================================
# STOP CONTROL FUNCTIONS
# ==========================================
def set_stop_flag(value: bool):
    """Set global stop flag"""
    global SHOULD_STOP
    SHOULD_STOP = value
    # If stopping, try to close driver immediately!
    if value and CURRENT_DRIVER:
        try:
            CURRENT_DRIVER.quit()
        except Exception:
            pass

def get_stop_flag() -> bool:
    """Check if we should stop"""
    global SHOULD_STOP
    return SHOULD_STOP

def set_current_driver(driver):
    """Store the current driver for instant kill"""
    global CURRENT_DRIVER
    CURRENT_DRIVER = driver

def check_stop() -> bool:
    """Check and raise exception if stop requested"""
    if get_stop_flag():
        raise InterruptedError("Scrape stopped by user!")
    return False

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def extract_next_data(soup):
    check_stop()
    for script in soup.find_all('script'):
        text = script.get_text()
        if '"props":{"pageProps"' in text:
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start != -1 and end > start:
                    data = json.loads(text[start:end])
                    if 'props' in data and 'pageProps' in data['props']:
                        return data
            except Exception:
                pass
    return None

def extract_phone(soup, next_data):
    check_stop()
    if next_data:
        try:
            rest_data = next_data['props']['pageProps']['results']['results']
            v_number = rest_data.get('VNumber', '')
            if v_number and len(v_number.replace('+', '').replace(' ', '')) >= 10:
                return v_number.replace('+91', '').replace(' ', '').strip()
        except Exception:
            pass

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if data.get('@type') == 'Restaurant':
                tel = data.get('telephone', '')
                if tel:
                    return tel.replace('+91', '').replace(' ', '').strip()
        except Exception:
            pass

    tel_links = soup.find_all('a', href=re.compile(r'^tel:'))
    for link in tel_links:
        href = link.get('href', '')
        num = href.replace('tel:', '').replace('+91', '').replace(' ', '').strip()
        if num and len(num) >= 10 and num.replace('+', '').isdigit():
            return num

    action_items = soup.find_all(class_=re.compile(r'action_item_text'))
    for item in action_items:
        text = item.get_text(strip=True)
        digits = re.sub(r'\D', '', text)
        if len(digits) >= 10:
            return digits

    return ""

def extract_menu(driver):
    check_stop()
    menu_items = []
    seen = set()

    # Step 1: Click the Menu tab
    try:
        print("      Looking for Menu tab...")
        menu_tabs = driver.find_elements(By.XPATH, "//div[contains(@class, 'jddetails_tabitem') and .//span[contains(text(), 'Menu')]] | //span[contains(text(), 'Menu')]/ancestor::div[contains(@class, 'tab')]")
        for tab in menu_tabs:
            check_stop()
            if tab.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tab)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", tab)
                print("      Clicked Menu tab, waiting for content to load...")
                time.sleep(4)
                break
    except Exception as e:
        print(f"      Warning: Could not click Menu tab: {e}")

    # Step 1.5: Click all "View All" accordion buttons to expand menu sections
    try:
        print("      Expanding accordion menu sections...")
        view_all_buttons = driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view all') or contains(@class, 'accordion_viewall') or contains(@class, 'accordion_item')]")
        for btn in view_all_buttons:
            check_stop()
            try:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
            except Exception:
                pass
        time.sleep(2)  # Wait for content to expand
    except Exception as e:
        print(f"      Warning: Could not expand accordions: {e}")

    # Step 3: Extract menu items from service_row elements (the correct ones!)
    print("      Scraping menu items with updated selectors...")
    
    for _ in range(25):  # Scroll a bit to load more items
        check_stop()
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all service_row elements
        service_rows = soup.find_all(attrs={"class": re.compile(r"service_row")})
        
        for row in service_rows:
            check_stop()
            # Find name
            name_el = row.find(attrs={"class": re.compile(r"service_name")})
            if not name_el:
                continue
            item_name = name_el.get_text(strip=True)
            if not item_name or len(item_name) < 2 or item_name.lower() in seen:
                continue
            
            # Find price
            price = "0"
            price_el = row.find(attrs={"class": re.compile(r"service_priceoffer")})
            if price_el:
                price_text = price_el.get_text(strip=True)
                price_match = re.search(r'(\d+)', price_text)
                if price_match:
                    price = price_match.group(1)
            
            # Find veg/non-veg
            is_veg = True
            tagbox = row.find(attrs={"class": re.compile(r"service_tagbox")})
            if tagbox:
                img = tagbox.find('img')
                if img:
                    alt = img.get('alt', '').lower()
                    src = img.get('src', '').lower()
                    if 'non' in alt or 'non' in src or 'egg' in alt or 'egg' in src:
                        is_veg = False
            
            seen.add(item_name.lower())
            menu_items.append({"name": item_name, "price": price, "is_veg": is_veg})
        
        # Also try original selectors as fallback
        fallback_selectors = [
            re.compile(r'catalogue_name'),
        ]
        for sel in fallback_selectors:
            elements = soup.find_all(attrs={"class": sel})
            for el in elements:
                check_stop()
                item_name = el.get_text(strip=True)
                if not item_name or len(item_name) < 2 or item_name.lower() in seen:
                    continue
                
                price = "0"
                parent = el.parent
                price_found = False
                for _ in range(5):
                    if not parent:
                        break
                    price_el = parent.find(attrs={"class": re.compile(r'catalogue_priceoffer')})
                    if price_el:
                        price_match = re.search(r'(\d+)', price_el.get_text(strip=True))
                        if price_match:
                            price = price_match.group(1)
                        price_found = True
                        break
                    parent = parent.parent
                
                is_veg = True
                # Find veg/non-veg
                parent = el.parent
                for _ in range(5):
                    if not parent:
                        break
                    tagbox = parent.find(attrs={"class": re.compile(r'catalogue_tagbox')})
                    if tagbox:
                        img = tagbox.find('img')
                        if img:
                            alt = img.get('alt', '').lower()
                            src = img.get('src', '').lower()
                            if 'non' in alt or 'non' in src or 'egg' in alt or 'egg' in src:
                                is_veg = False
                        break
                    parent = parent.parent
                
                seen.add(item_name.lower())
                menu_items.append({"name": item_name, "price": price, "is_veg": is_veg})
        
        # Scroll a little
        driver.execute_script("window.scrollBy(0, 350);")
        time.sleep(0.4)

    return menu_items

def scrape_gallery_images(driver, base_restaurant_url):
    check_stop()
    clean_url = base_restaurant_url.split('?')[0].rstrip('/')
    gallery_url = f"{clean_url}/gallery?type=all"

    print(f"      Navigating to Gallery: {gallery_url}")
    driver.get(gallery_url)
    time.sleep(5)
    check_stop()

    categories_to_scrape = ['Food', 'Ambience', 'By User', 'Drink', 'All']
    scraped_data = {cat: [] for cat in categories_to_scrape}
    seen_urls = set()

    for cat in categories_to_scrape:
        check_stop()
        print(f"         Scanning category: {cat}...")

        if cat != 'All':
            tabs = driver.find_elements(By.XPATH, f"//*[contains(text(), '{cat}') or contains(@class, 'tab_item')]")
            clicked = False
            for tab in tabs:
                check_stop()
                try:
                    if tab.is_displayed():
                        driver.execute_script("arguments[0].click();", tab)
                        time.sleep(3)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                continue
        else:
            driver.get(gallery_url)
            time.sleep(4)
            check_stop()

        for _ in range(5):
            check_stop()
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for img in soup.find_all('img'):
            check_stop()
            src = img.get('src') or img.get('data-src')
            if src and 'jdmagicbox.com' in src and ('catalogue' in src or 'menu' in src):
                clean_src = src.split('?')[0] if '?' in src else src
                if clean_src not in seen_urls:
                    scraped_data[cat].append(clean_src)
                    seen_urls.add(clean_src)

    return scraped_data

def wait_for_page_load(driver, timeout=120):  # 2 minutes instead of 5
    check_stop()
    print("\n" + "="*60)
    print("IMPORTANT: Solve CAPTCHA in the Chrome window that opens!")
    print("="*60)
    print("\nThe scraper will automatically detect when the page loads properly.")
    print("No need to press Enter - just solve the CAPTCHA and the scraper will continue!")
    print(f"\nTimeout after 2 minutes if no page loads.")

    start_time = time.time()
    while time.time() - start_time < timeout:
        check_stop()
        try:
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            all_links = soup.find_all('a', href=True)
            has_business_links = False
            for link in all_links:
                href = link.get('href', '')
                if ('_BZDET' in href or '/Restaurants/' in href or '/restaurants/' in href.lower() or any(subcat in href.lower() for subcat in ['hotels', 'beauty', 'car', 'doctor', 'school'])):
                    has_business_links = True
                    break

            if has_business_links:
                print("\nGreat! Page loaded successfully. Starting scrape...")
                time.sleep(2)
                return True

            print(f"Waiting for page to load... ({int(time.time() - start_time)}s elapsed) (Solve CAPTCHA if visible!)", end='\r')
            time.sleep(1.5)
        except Exception:
            time.sleep(1.5)

    print("\nTimeout waiting for page to load. Please try again with a different category/city.")
    return False

# ==========================================
# CORE SCRAPING LOGIC
# ==========================================
def process_single_restaurant(driver, restaurant_url, category_name="Restaurants"):
    check_stop()
    print(f"\n--------------------------------------------------")
    print(f"Processing: {restaurant_url}")
    driver.get(restaurant_url)
    time.sleep(4)
    check_stop()

    for _ in range(6):
        check_stop()
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(1.5)

    try:
        show_buttons = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show number') or contains(@class, 'call') or contains(@class, 'phone')]")
        for btn in show_buttons:
            check_stop()
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.5)
    except Exception:
        pass

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    next_data = extract_next_data(soup)

    details = {
        'name': 'Unknown Business', 'phone': '', 'whatsapp': '', 'address': '',
        'opening_hours': '', 'url': restaurant_url, 'menu': [], 'amenities': {}
    }

    if next_data:
        try:
            rest_data = next_data['props']['pageProps']['results']['results']
            details['name'] = rest_data.get('name', details['name'])
            details['address'] = rest_data.get('address', '')
            details['opening_hours'] = rest_data.get('HoursOfOperation', '')

            msg_num_str = rest_data.get('msg_num', '')
            if msg_num_str:
                try:
                    msg_num_data = json.loads(msg_num_str)
                    wup_list = msg_num_data.get('wup', [])
                    if wup_list and wup_list[0]:
                        details['whatsapp'] = wup_list[0]
                except Exception:
                    pass

            services_data = rest_data.get('services', {})
            if isinstance(services_data, dict):
                for category, items in services_data.items():
                    check_stop()
                    if isinstance(items, list):
                        details['amenities'][category] = [item.get('att', '') for item in items if item.get('att')]
            # If services is a list, handle that too
            elif isinstance(services_data, list):
                for i, item in enumerate(services_data):
                    check_stop()
                    if isinstance(item, dict) and 'att' in item:
                        details['amenities'][f"Amenity {i+1}"] = item.get('att', '')
        except KeyError:
            pass

    details['phone'] = extract_phone(soup, next_data)

    if not details['address']:
        addr_el = soup.find('address', class_=re.compile(r'vendorinfo_address')) or soup.find('span', class_='adresstooltip')
        if addr_el:
            details['address'] = addr_el.get_text(strip=True)

    if not details['opening_hours']:
        if next_data:
            try:
                hop_data = next_data['props']['pageProps']['results']['results'].get('hop', {})
                hop_list = hop_data.get('hop', [])
                if hop_list:
                    details['opening_hours'] = hop_list[0].get('hours', '')
            except Exception:
                pass

    if details['name'] == 'Unknown Business':
        name_elem = soup.select_one('h1')
        if name_elem:
            details['name'] = name_elem.get_text(strip=True)
        else:
            print("   Could not find business name")
            return False

    details['menu'] = extract_menu(driver)

    print(f"   Name: {details['name']}")
    print(f"   Phone: {details['phone'] or 'Not found'}")
    print(f"   WhatsApp: {details['whatsapp'] or 'Not found'}")
    print(f"   Address: {details['address'][:50] + '...' if len(details['address']) > 50 else details['address']}")
    print(f"   Hours: {details['opening_hours'] or 'Not found'}")
    print(f"   Menu Items Found: {len(details['menu'])}")

    scraped_categories = scrape_gallery_images(driver, restaurant_url)
    final_images_to_download = []

    for cat in ['Food', 'Ambience', 'By User', 'Drink']:
        check_stop()
        urls = scraped_categories.get(cat, [])
        for url in urls[:10]:
            final_images_to_download.append((cat, url))

    remaining_needed = 50 - len(final_images_to_download)
    if remaining_needed > 0:
        all_urls = scraped_categories.get('All', [])
        for url in all_urls[:remaining_needed]:
            check_stop()
            final_images_to_download.append(('General', url))

    downloaded_paths = []
    downloaded_categories = []

    safe_name = "".join(c for c in details['name'] if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')

    if final_images_to_download:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.justdial.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
        }
        cat_counts = {'Food': 0, 'Ambience': 0, 'By User': 0, 'Drink': 0, 'General': 0}

        for cat_name, img_url in final_images_to_download:
            check_stop()
            try:
                img_response = requests.get(img_url, headers=headers, timeout=10)
                if img_response.status_code == 200:
                    cat_counts[cat_name] += 1
                    safe_cat_name = cat_name.replace(' ', '')
                    filename = f"{safe_name}_{safe_cat_name}_{cat_counts[cat_name]}.jpg"
                    image_path = os.path.join(LOCAL_IMAGE_FOLDER, filename)
                    with open(image_path, 'wb') as f:
                        f.write(img_response.content)
                    downloaded_paths.append(image_path)
                    downloaded_categories.append(cat_name)
            except Exception:
                pass

    print("   Uploading complete payload to API...")
    data = {
        'name': details['name'], 'phone': details['phone'] or "",
        'whatsapp': details['whatsapp'] or "", 'address': details['address'] or "",
        'opening_hours': details['opening_hours'] or "", 'source_url': details['url'],
        'category': category_name,
        'menu_json': json.dumps(details['menu']),
        'amenities_json': json.dumps(details['amenities']),
        'image_categories': json.dumps(downloaded_categories)
    }

    files = []
    for path in downloaded_paths:
        files.append(('images', (os.path.basename(path), open(path, 'rb'))))

    try:
        response = requests.post(API_UPLOAD_URL, files=files if files else None, data=data, timeout=45)

        for _, file_tuple in files:
            file_tuple[1].close()

        if response.status_code in [200, 201]:
            print("   Successfully uploaded!")
            return True
        else:
            print(f"   Upload failed: {response.status_code}")
            return False
    except Exception as e:
        for _, file_tuple in files:
            try:
                file_tuple[1].close()
            except Exception:
                pass
        print(f"   Error uploading: {e}")
        return False

def get_existing_businesses():
    """Get all existing businesses from DB once"""
    try:
        response = requests.get("http://localhost:8000/api/v1/restaurants", timeout=5)
        if response.ok:
            return response.json()
    except Exception:
        pass
    return []


def is_business_duplicate(candidate_name, candidate_url, existing):
    """Check if business is duplicate by name OR phone OR address OR URL"""
    for r in existing:
        # Check by name (case-insensitive)
        if candidate_name and r.get("name", "").lower() == candidate_name.lower():
            return True, r.get("name", "")
        # Check by URL
        if candidate_url and r.get("jd_url", "") == candidate_url:
            return True, r.get("name", "")
        # Check by phone (if available)
        if r.get("phone"):
            pass  # We don't have candidate phone yet, will check after scraping
    return False, ""


def scrape_city(city_name, category="Restaurants", subcategory=None, max_limit=None):
    global SHOULD_STOP
    SHOULD_STOP = False
    full_category = f"{category}" + (f" - {subcategory}" if subcategory else "")
    print(f"\n==================================================================")
    print(f"Starting new city: {city_name.upper()} | Category: {full_category} | Limit: {max_limit}")
    print(f"==================================================================")

    success_count = 0
    driver = None

    # Build category URL and show it!
    from .category_fetcher import build_search_url
    search_url = build_search_url(city_name, category, subcategory)
    print(f"\nTrying URL: {search_url}")

    options = uc.ChromeOptions()
    # Smaller window size instead of maximized
    options.add_argument("--window-size=1024,768")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir={user_data_dir}")

    try:
        driver = uc.Chrome(
            options=options,
            patcher_kwargs={"target_dir": driver_dir}
        )
        set_current_driver(driver)

        print(f"\nStep 1: Scraping search results for {city_name}...")
        driver.get(search_url)
        time.sleep(5)
        check_stop()

        if not wait_for_page_load(driver, timeout=120):
            return

        for _ in range(5):
            check_stop()
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        filtered_businesses = []
        seen_urls = set()

        # Find business links with names from search page
        for a_tag in soup.find_all('a', href=True):
            check_stop()
            href = a_tag['href']
            if f'/{city_name}/' not in href.lower() or 'nct-' in href.lower() or href.endswith(f'/{city_name}/'):
                continue
            
            # Build full URL
            full_url = f"https://www.justdial.com{href}" if href.startswith('/') else href
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Extract business name from link text or nearby elements
            name = ""
            try:
                text = a_tag.get_text(strip=True)
                if len(text) > 3:
                    name = text
                else:
                    # Try getting text from parent/children
                    name = a_tag.find_parent().get_text(strip=True)[:60]
            except Exception:
                pass
            
            filtered_businesses.append({"url": full_url, "name": name})

        # Also add _BZDET links
        all_bzdet_links = re.findall(r'href="([^"]*_BZDET[^"]*)"', driver.page_source)
        for link in all_bzdet_links:
            check_stop()
            full_link = f"https://www.justdial.com{link}" if link.startswith('/') else link
            if full_link not in seen_urls:
                seen_urls.add(full_link)
                filtered_businesses.append({"url": full_link, "name": ""})
        
        # Get existing businesses ONCE
        existing = get_existing_businesses()
        existing_names = {r.get("name", "").lower() for r in existing}
        existing_urls = {r.get("jd_url", "") for r in existing}

        print(f"Found {len(filtered_businesses)} businesses in {city_name}.")
        if len(filtered_businesses) == 0:
            print("No businesses found. The page might still be blocked or category is wrong.")
            return

        # Filter out duplicates early
        unique_businesses = []
        for bus in filtered_businesses:
            name = bus.get("name", "").lower()
            url = bus.get("url", "")
            if name in existing_names or url in existing_urls:
                continue
            unique_businesses.append(bus)
        
        print(f"Found {len(unique_businesses)} new businesses, skipping {len(filtered_businesses)-len(unique_businesses)} duplicates!")
        
        if len(unique_businesses) == 0:
            print("All businesses are already scraped!")
            return

        if max_limit and max_limit != 'All' and max_limit != 'None' and max_limit is not None:
            try:
                max_businesses = min(int(max_limit), len(unique_businesses))
            except ValueError:
                max_businesses = len(unique_businesses)
        else:
            max_businesses = len(unique_businesses)
        
        print(f"Scraping {max_businesses} new businesses...")
        
        for index, bus in enumerate(unique_businesses[:max_businesses]):
            check_stop()
            try:
                business_url = bus.get("url", "")
                business_name = bus.get("name", "")
                
                if process_single_restaurant(driver, business_url, full_category):
                    success_count += 1
                time.sleep(3)
            except Exception as e:
                    print(f"   Error processing business: {e}")
                    continue

        print(f"\nCompleted {city_name}! Successfully uploaded {success_count}/{max_businesses} businesses.")

    except InterruptedError:
        print(f"\n✅ STOPPED BY USER!")
    except Exception as e:
        print(f"Fatal error in {city_name}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        set_current_driver(None)
        print(f"Browser closed.")

def scrape_single_url(restaurant_url):
    global SHOULD_STOP
    SHOULD_STOP = False
    print(f"\n==================================================================")
    print(f"Scraping single URL: {restaurant_url}")
    print(f"==================================================================")

    driver = None
    options = uc.ChromeOptions()
    # Smaller window size instead of maximized
    options.add_argument("--window-size=1024,768")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir={user_data_dir}")

    try:
        print("Launching Chrome...")
        driver = uc.Chrome(
            options=options,
            patcher_kwargs={"target_dir": driver_dir}
        )
        set_current_driver(driver)

        print("Navigating to URL...")
        driver.get(restaurant_url)
        time.sleep(5)
        check_stop()

        print("\n" + "="*60)
        print("Solve any CAPTCHA in the Chrome window!")
        print("The scraper will automatically continue when the page loads.")
        print("="*60)
        time.sleep(5)
        check_stop()

        success = process_single_restaurant(driver, restaurant_url)
        if success:
            print(f"\nSuccessfully scraped and uploaded!")
        else:
            print(f"\nFailed to scrape!")
        return success

    except InterruptedError:
        print(f"\n✅ STOPPED BY USER!")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        set_current_driver(None)
        print(f"Browser closed.")

def scrape_and_upload():
    print("Starting multi-city Kerala master scraper...")
    for city in KERALA_CITIES:
        scrape_city(city)
        print("Taking a 10-second breather before the next city...")
        time.sleep(10)
    print("\nAll cities completed! Scraper run finished.")

if __name__ == "__main__":
    scrape_and_upload()
