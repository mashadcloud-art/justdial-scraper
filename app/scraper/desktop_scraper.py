import os
import time
import json
import re
import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc 
from selenium.webdriver.common.by import By 

# ==========================================
# CONFIGURATION
# ==========================================
API_UPLOAD_URL = "http://localhost:8000/api/v1/upload-restaurant"
LOCAL_IMAGE_FOLDER = "./scraped_images"

KERALA_CITIES = [
    "Kochi", "Thiruvananthapuram", "Kozhikode", "Thrissur", "Kollam",
    "Kannur", "Palakkad", "Alappuzha", "Kottayam"
]

os.makedirs(LOCAL_IMAGE_FOLDER, exist_ok=True)

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def extract_next_data(soup):
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
    """Strictly extracts phone numbers, ignoring buttons like 'Order Online'"""
    if next_data:
        try:
            rest_data = next_data['props']['pageProps']['results']['results']
            v_number = rest_data.get('VNumber', '')
            if v_number and len(v_number.replace('+', '').replace(' ', '')) >= 10:
                return v_number.replace('+91', '').replace(' ', '').strip()
        except: pass

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if data.get('@type') == 'Restaurant':
                tel = data.get('telephone', '')
                if tel: return tel.replace('+91', '').replace(' ', '').strip()
        except: pass

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
    """🟢 PERFECT MENU EXTRACTION: Defeats React Virtual DOM by parsing while scrolling"""
    menu_items = []
    seen = set()
    menu_found = False
    
    # 1. Scroll to Menu section broadly
    try:
        menu_headings = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'menu')]")
        for heading in menu_headings:
            if heading.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", heading)
                time.sleep(2)
                menu_found = True
                break
    except: pass

    # 2. Expand any "View all" buttons or Accordions
    try:
        view_all_buttons = driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view all') or contains(@class, 'accordion_viewall')]")
        for btn in view_all_buttons:
            try:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1.5) # Wait for items to expand
            except: pass
    except: pass

    # 3. Scroll back to the top of the menu before parsing
    if menu_found:
        try:
            menu_headings = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'menu')]")
            for heading in menu_headings:
                if heading.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'start'});", heading)
                    time.sleep(1)
                    break
        except: pass
    else:
        driver.execute_script("window.scrollTo(0, 0);")

    # 4. 🟢 VIRTUAL DOM BYPASS: Parse the HTML at EVERY scroll step using direct name targeting
    print("      📜 Scraping menu items while scrolling (handling virtual DOM)...")
    
    driver.execute_script("window.scrollBy(0, -200);")
    time.sleep(1)

    for _ in range(40): # Loop to slowly step down the menu
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Look for the name directly, bypassing dynamic wrapper classes
        name_elements = soup.find_all(attrs={"class": re.compile(r'service_name|catalogue_name')})
        
        for name_el in name_elements:
            item_name = name_el.get_text(strip=True)
            if not item_name or item_name.lower() in seen: 
                continue
            
            price = "0"
            is_veg = True
            
            # Traverse up the DOM to find the associated price and veg icon
            parent = name_el.parent
            price_found = False
            veg_found = False
            
            for _ in range(5): # Go up to 5 levels deep
                if not parent: 
                    break
                
                if not price_found:
                    price_el = parent.find(attrs={"class": re.compile(r'service_priceoffer|catalogue_priceoffer')})
                    if price_el:
                        price_match = re.search(r'(\d+)', price_el.get_text(strip=True))
                        if price_match: price = price_match.group(1)
                        price_found = True
                        
                if not veg_found:
                    tagbox = parent.find(attrs={"class": re.compile(r'service_tagbox|catalogue_tagbox')})
                    if tagbox:
                        img = tagbox.find('img')
                        if img:
                            alt = img.get('alt', '').lower()
                            if 'non' in alt or 'egg' in alt: is_veg = False
                        veg_found = True
                        
                if price_found and veg_found: 
                    break
                parent = parent.parent
                
            seen.add(item_name.lower())
            menu_items.append({"name": item_name, "price": price, "is_veg": is_veg})
            
        # Scroll down by exactly the height of a few items to trigger the next React render batch
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(0.5) # Wait for DOM to update

    return menu_items

def scrape_gallery_images(driver, base_restaurant_url):
    clean_url = base_restaurant_url.split('?')[0].rstrip('/')
    gallery_url = f"{clean_url}/gallery?type=all"
    
    print(f"      📸 Navigating to Gallery: {gallery_url}")
    driver.get(gallery_url)
    time.sleep(5) 
    
    categories_to_scrape = ['Food', 'Ambience', 'By User', 'Drink', 'All']
    scraped_data = {cat: [] for cat in categories_to_scrape}
    seen_urls = set()
    
    for cat in categories_to_scrape:
        print(f"         🔎 Scanning category: {cat}...")
        
        if cat != 'All':
            tabs = driver.find_elements(By.XPATH, f"//*[contains(text(), '{cat}') or contains(@class, 'tab_item')]")
            clicked = False
            for tab in tabs:
                try:
                    if tab.is_displayed():
                        driver.execute_script("arguments[0].click();", tab)
                        time.sleep(3) 
                        clicked = True
                        break
                except: continue
            if not clicked: continue
        else:
            driver.get(gallery_url)
            time.sleep(4)
        
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src and 'jdmagicbox.com' in src and ('catalogue' in src or 'menu' in src):
                clean_src = src.split('?')[0] if '?' in src else src
                if clean_src not in seen_urls:
                    scraped_data[cat].append(clean_src)
                    seen_urls.add(clean_src)
                    
    return scraped_data

# ==========================================
# CORE SCRAPING LOGIC
# ==========================================
def scrape_city(city_name, max_limit=None):
    print(f"\n=================================================================")
    print(f"🌴 STARTING NEW CITY: {city_name.upper()} (Limit: {max_limit})")
    print(f"=================================================================")
    
    success_count = 0
    search_url = f"https://www.justdial.com/{city_name}/Restaurants/nct-10408936"
    
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    scraper_profile_path = os.path.join(project_root, "scraper_chrome_profile")
    
    options.add_argument(f"--user-data-dir={scraper_profile_path}")
    options.add_argument("--profile-directory=Default") 
    
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        print(f"❌ Failed to start browser for {city_name}: {e}")
        return
        
    try:
        print(f"📋 STEP 1: Scraping search results for {city_name}...")
        driver.get(search_url)
        time.sleep(5) # Give it a moment to load initially
        
        # 🛑 PAUSE FOR MANUAL CAPTCHA SOLVING
        print("\n" + "="*60)
        print("⚠️  CHECK THE CHROME BROWSER WINDOW!")
        print("If JustDial is showing a CAPTCHA or 'Verify you are human',")
        print("please solve it manually in the browser right now.")
        print("Once you can see the actual list of restaurants,")
        print("come back here and press ENTER to continue...")
        print("="*60)
        input()
        
        # Scroll to load results
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        restaurant_urls = []

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if f'/{city_name}/' in href and 'nct-' not in href and not href.endswith(f'/{city_name}/'):
                link = f"https://www.justdial.com{href}" if href.startswith('/') else href
                if link not in restaurant_urls and 'http' in link:
                    restaurant_urls.append(link)

        all_bzdet_links = re.findall(r'href="([^"]*_BZDET[^"]*)"', driver.page_source)
        for link in all_bzdet_links:
            full_link = f"https://www.justdial.com{link}" if link.startswith('/') else link
            if full_link not in restaurant_urls and 'nct-' not in full_link:
                restaurant_urls.append(full_link)
                
        print(f"📦 Found {len(restaurant_urls)} restaurants in {city_name}.")
        if len(restaurant_urls) == 0: 
            print("⚠️ No restaurants found. The page might still be blocked.")
            return
            
        if max_limit and max_limit != 'All' and max_limit != 'None':
            try: max_restaurants = min(int(max_limit), len(restaurant_urls))
            except ValueError: max_restaurants = len(restaurant_urls)
        else:
            max_restaurants = len(restaurant_urls)
            
        print(f"🎯 Scraping {max_restaurants} restaurants...")
        
        for index, restaurant_url in enumerate(restaurant_urls[:max_restaurants]):
            try:
                print(f"\n--------------------------------------------------")
                print(f"🏪 [{city_name}] [{index+1}/{max_restaurants}] Main Page: {restaurant_url}")
                driver.get(restaurant_url)
                time.sleep(4) 
                
                for _ in range(6):
                    driver.execute_script("window.scrollBy(0, 600);")
                    time.sleep(1.5)
                
                try:
                    show_buttons = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show number') or contains(@class, 'call') or contains(@class, 'phone')]")
                    for btn in show_buttons:
                        if btn.is_displayed():
                            driver.execute_script("arguments[0].click();", btn)
                            time.sleep(1.5) 
                except Exception: pass 

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                next_data = extract_next_data(soup)
                
                details = {
                    'name': 'Unknown Restaurant', 'phone': '', 'whatsapp': '', 'address': '',
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
                                if wup_list and wup_list[0]: details['whatsapp'] = wup_list[0]
                            except: pass
                                
                        services_data = rest_data.get('services', {})
                        for category, items in services_data.items():
                            if isinstance(items, list):
                                details['amenities'][category] = [item.get('att', '') for item in items if item.get('att')]
                    except KeyError: pass
                
                details['phone'] = extract_phone(soup, next_data)
                
                if not details['address']:
                    addr_el = soup.find('address', class_=re.compile(r'vendorinfo_address')) or soup.find('span', class_='adresstooltip')
                    if addr_el: details['address'] = addr_el.get_text(strip=True)
                    
                if not details['opening_hours']:
                    if next_data:
                        try:
                            hop_data = next_data['props']['pageProps']['results']['results'].get('hop', {})
                            hop_list = hop_data.get('hop', [])
                            if hop_list:
                                details['opening_hours'] = hop_list[0].get('hours', '')
                        except: pass
                
                if details['name'] == 'Unknown Restaurant':
                    name_elem = soup.select_one('h1')
                    if name_elem: details['name'] = name_elem.get_text(strip=True)
                    else: continue

                # 🟢 EXTRACT COMPLETE MENU (Scrolls & Clicks View All)
                details['menu'] = extract_menu(driver)

                print(f"   📝 Name: {details['name']}")
                print(f"   📞 Phone: {details['phone'] or 'Not found'}")
                print(f"   💬 WhatsApp: {details['whatsapp'] or 'Not found'}")
                print(f"   📍 Address: {details['address'][:50] + '...' if len(details['address']) > 50 else details['address']}")
                print(f"   ⏰ Hours: {details['opening_hours'] or 'Not found'}")
                print(f"   📋 Menu Items Found: {len(details['menu'])}")
                
                scraped_categories = scrape_gallery_images(driver, restaurant_url)
                final_images_to_download = []
                
                for cat in ['Food', 'Ambience', 'By User', 'Drink']:
                    urls = scraped_categories.get(cat, [])
                    for url in urls[:10]: final_images_to_download.append((cat, url))
                        
                remaining_needed = 50 - len(final_images_to_download)
                if remaining_needed > 0:
                    all_urls = scraped_categories.get('All', [])
                    for url in all_urls[:remaining_needed]: final_images_to_download.append(('General', url))
                
                downloaded_paths = []
                downloaded_categories = []
                
                # 🟢 SMART IMAGE NAMING: RestaurantName_Category_1.jpg
                safe_name = "".join(c for c in details['name'] if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')
                
                if final_images_to_download:
                    # 🟢 FIXED: Added realistic headers to stop JD from blocking images (403 Forbidden)
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': 'https://www.justdial.com/',
                        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
                    }
                    cat_counts = {'Food': 0, 'Ambience': 0, 'By User': 0, 'Drink': 0, 'General': 0}
                    
                    for cat_name, img_url in final_images_to_download:
                        try:
                            img_response = requests.get(img_url, headers=headers, timeout=10)
                            if img_response.status_code == 200:
                                cat_counts[cat_name] += 1
                                safe_cat_name = cat_name.replace(' ', '') # e.g., ByUser
                                filename = f"{safe_name}_{safe_cat_name}_{cat_counts[cat_name]}.jpg"
                                image_path = os.path.join(LOCAL_IMAGE_FOLDER, filename)
                                with open(image_path, 'wb') as f: f.write(img_response.content)
                                downloaded_paths.append(image_path)
                                downloaded_categories.append(cat_name)
                        except Exception: pass 
                            
                print("   ☁️ Uploading complete payload to API...")
                data = {
                    'name': details['name'], 'phone': details['phone'] or "", 
                    'whatsapp': details['whatsapp'] or "", 'address': details['address'] or "", 
                    'opening_hours': details['opening_hours'] or "", 'source_url': details['url'],
                    'menu_json': json.dumps(details['menu']),
                    'amenities_json': json.dumps(details['amenities']),
                    'image_categories': json.dumps(downloaded_categories)
                }
                
                files = []
                for path in downloaded_paths:
                    files.append(('images', (os.path.basename(path), open(path, 'rb'))))
                
                response = requests.post(API_UPLOAD_URL, files=files if files else None, data=data, timeout=45)
                
                for _, file_tuple in files: file_tuple[1].close()
                
                if response.status_code in [200, 201]:
                    print("   ✅ Successfully uploaded!")
                    success_count += 1
                else:
                    print(f"   ❌ Upload failed: {response.status_code}")
                
                time.sleep(3)
                
            except Exception as e:
                print(f"   ⚠️ Error processing restaurant: {e}")
                continue
        
        print(f"\n🎉 COMPLETED {city_name}! Successfully uploaded {success_count}/{max_restaurants} restaurants.")

    except Exception as e:
        print(f"🔥 Fatal Error in {city_name}: {e}")
    finally:
        driver.quit()
        print(f"🏁 Browser closed for {city_name}.")

def scrape_and_upload():
    print("🚀 INIT: Starting Multi-City Kerala Master Scraper...")
    for city in KERALA_CITIES:
        scrape_city(city)
        print("⏳ Taking a 10-second breather before the next city...")
        time.sleep(10)
    print("\n🏆 ALL CITIES COMPLETED! Scraper run finished.")

if __name__ == "__main__":
    scrape_and_upload()