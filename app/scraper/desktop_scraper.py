from app.scraper.logger import log
import os
import re
import time
import json
from contextlib import ExitStack
from typing import Dict, List, Set

import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium import webdriver
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# ==========================================
# CONFIGURATION
# ==========================================
API_UPLOAD_URL = os.getenv("API_UPLOAD_URL", "http://localhost:8000/api/v1/upload-restaurant")
LOCAL_IMAGE_FOLDER = os.getenv("LOCAL_IMAGE_FOLDER", "./scraped_images")
TARGET_DISTRICTS = [
    "https://www.justdial.com/Kasaragod/Restaurants/nct-10408936",
]
MAX_PAGES = int(os.getenv("MAX_PAGES", "100"))
MAX_IMAGES_PER_CATEGORY = 10
MAX_TOTAL_IMAGES = 50
DEFAULT_WAIT = int(os.getenv("DEFAULT_WAIT", "20"))
SCROLL_PAUSE = float(os.getenv("SCROLL_PAUSE", "1.0"))
MANUAL_CAPTCHA = os.getenv("MANUAL_CAPTCHA", "false").lower() == "true"
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
USE_PROFILE = os.getenv("USE_PROFILE", "false").lower() == "true"
PROFILE_DIR_NAME = os.getenv("PROFILE_DIR_NAME", "Default")

os.makedirs(LOCAL_IMAGE_FOLDER, exist_ok=True)


# ==========================================
# HTTP SESSION WITH RETRIES
# ==========================================
def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3, read=3, connect=3, backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    return session

SESSION = build_session()


# ==========================================
# HELPERS
# ==========================================
def wait_for_body(driver, timeout=DEFAULT_WAIT):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

def safe_get(driver, url: str, timeout=DEFAULT_WAIT):
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

def click_if_present(driver, xpath: str, pause=1.0):
    try:
        elements = driver.find_elements(By.XPATH, xpath)
        for el in elements:
            try:
                if el.is_displayed() and el.is_enabled():
                    driver.execute_script("arguments[0].click();", el)
                    time.sleep(pause)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False

def click_all_present(driver, xpath: str, pause=1.0):
    clicked_any = False
    try:
        elements = driver.find_elements(By.XPATH, xpath)
        for el in elements:
            try:
                if el.is_displayed() and el.is_enabled():
                    driver.execute_script("arguments[0].click();", el)
                    time.sleep(pause)
                    clicked_any = True
            except Exception:
                continue
    except Exception:
        pass
    return clicked_any

def clean_phone(value: str) -> str:
    return re.sub(r"\D+", "", value or "").lstrip("91")

def safe_filename(name: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _-]+", "", name or "Unknown").strip().replace(" ", "_")
    return (cleaned or "Unknown")[:max_len]


# ==========================================
# JSON EXTRACTION
# ==========================================
def extract_json_ld_data(soup: BeautifulSoup) -> Dict:
    next_script = soup.find("script", id="__NEXT_DATA__")
    if not next_script or not next_script.string:
        return {}
    try:
        data = json.loads(next_script.string)
        res = data.get("props", {}).get("pageProps", {}).get("results", {}).get("results", {})
        if not isinstance(res, dict):
            return {}

        extracted = {
            "name": res.get("name", ""),
            "phone": clean_phone(res.get("VNumber", "")),
            "address": res.get("address", ""),
            "opening_hours": res.get("HoursOfOperation", ""),
            "amenities": {},
        }

        msg_num_str = res.get("msg_num", "")
        if msg_num_str:
            try:
                wup_list = json.loads(msg_num_str).get("wup", [])
                if wup_list:
                    wup_phone = clean_phone(str(wup_list[0]))
                    extracted["whatsapp"] = wup_phone
                    if not extracted["phone"] and wup_phone:
                        extracted["phone"] = wup_phone
            except Exception:
                pass

        services_data = res.get("services", {}) or {}
        if isinstance(services_data, dict):
            for category, items in services_data.items():
                if isinstance(items, list):
                    extracted["amenities"][category] = [
                        i.get("att", "") for i in items
                        if isinstance(i, dict) and i.get("att")
                    ]
        return extracted
    except Exception as e:
        log(f"      ⚠️ Error parsing __NEXT_DATA__: {e}")
        return {}


# ==========================================
# PAGINATION
# ==========================================
def extract_links_from_page(driver) -> List[str]:
    page_urls: List[str] = []
    seen: Set[str] = set()
    soup = BeautifulSoup(driver.page_source, "html.parser")
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if "_BZDET" not in href:
            continue
        if not href.startswith("http"):
            href = f"https://www.justdial.com{href}"
        href = href.split("?")[0].rstrip("/")
        if href not in seen:
            seen.add(href)
            page_urls.append(href)
    return page_urls

def get_all_paginated_urls(driver, base_url: str) -> List[str]:
    all_urls: List[str] = []
    seen_all: Set[str] = set()
    empty_or_repeat_pages = 0

    for page_num in range(1, MAX_PAGES + 1):
        current_url = base_url if page_num == 1 else f"{base_url}/page-{page_num}"
        log(f"   📄 Scraping page {page_num}: {current_url}")
        try:
            safe_get(driver, current_url)
            scroll_until_stable(driver, max_rounds=6)
            page_urls = extract_links_from_page(driver)
        except Exception as e:
            log(f"      ⚠️ Failed page {page_num}: {e}")
            break

        new_count = 0
        for url in page_urls:
            if url not in seen_all:
                seen_all.add(url)
                all_urls.append(url)
                new_count += 1

        log(f"      ✅ Found {len(page_urls)} links, {new_count} new. Total: {len(all_urls)}")

        if not page_urls or new_count == 0:
            empty_or_repeat_pages += 1
        else:
            empty_or_repeat_pages = 0

        if empty_or_repeat_pages >= 2:
            log("   🛑 Repeated/empty pages twice. Stopping pagination.")
            break

    return all_urls


# ==========================================
# MENU + GALLERY
# ==========================================
def extract_menu(driver) -> List[Dict]:
    menu_items = []
    seen = set()

    click_if_present(driver, "//*[contains(text(), 'Order Online Menu') or @id='dochead']", pause=1.5)
    click_all_present(driver, "//button[contains(@class, 'accordion_viewall')]", pause=0.5)
    
    # Wait a bit longer for all accordions to load their content
    time.sleep(2.0)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    rows = soup.find_all("div", class_=re.compile(r"service_row|catalogue_txtbox"))

    for row in rows:
        name_el = row.find("div", class_=re.compile(r"service_name|catalogue_name"))
        if not name_el:
            continue
        item_name = name_el.get_text(strip=True)
        key = item_name.lower()
        if not item_name or key in seen:
            continue

        price = "0"
        price_el = row.find("div", class_=re.compile(r"service_priceoffer|catalogue_priceoffer"))
        if price_el:
            match = re.search(r"(\d+)", price_el.get_text(" ", strip=True))
            if match:
                price = match.group(1)

        is_veg = True
        tagbox = row.find("div", class_=re.compile(r"service_tagbox|catalogue_tagbox"))
        if tagbox:
            img = tagbox.find("img")
            if img:
                alt = (img.get("alt") or "").lower()
                if "non" in alt or "egg" in alt:
                    is_veg = False

        seen.add(key)
        menu_items.append({"name": item_name, "price": price, "is_veg": is_veg})

    return menu_items

def scrape_gallery_images(driver, base_restaurant_url: str) -> Dict[str, List[str]]:
    clean_url = base_restaurant_url.split("?")[0].rstrip("/")
    gallery_url = f"{clean_url}/gallery?type=all"
    categories_to_scrape = ["Food", "Ambience", "By User", "Drink", "All"]
    scraped_data = {cat: [] for cat in categories_to_scrape}
    seen_urls = set()

    try:
        safe_get(driver, gallery_url)
    except Exception:
        return scraped_data

    for cat in categories_to_scrape:
        try:
            if cat != "All":
                click_if_present(driver, f"//*[contains(text(), '{cat}')]", pause=1.5)
            else:
                safe_get(driver, gallery_url)

            scroll_until_stable(driver, max_rounds=5)
            soup = BeautifulSoup(driver.page_source, "html.parser")

            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if "jdmagicbox.com" in src and ("catalogue" in src or "menu" in src):
                    clean_src = src.split("?")[0]
                    if clean_src not in seen_urls:
                        seen_urls.add(clean_src)
                        scraped_data[cat].append(clean_src)
        except Exception:
            continue

    return scraped_data


# ==========================================
# SCRAPE DETAILS
# ==========================================
def scrape_restaurant_details(driver, restaurant_url: str) -> Dict:
    safe_get(driver, restaurant_url)
    
    # Check for blank page or bot block — skip immediately
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
        page_title = driver.title.lower()
        current_url = driver.current_url.lower()
        
        # Detect blank/blocked page
        if (len(body_text) < 50 or 
            "action required" in page_title or
            "captcha" in body_text.lower() or
            "access denied" in body_text.lower() or
            "blocked" in body_text.lower() or
            "justdial.com/login" in current_url):
            log(f"   ⚠️ Blank or blocked page detected — skipping: {restaurant_url}")
            return {}
    except Exception:
        pass
    
    # Extract NEXT_DATA immediately before any clicks trigger modals or CAPTCHA
    soup = BeautifulSoup(driver.page_source, "html.parser")
    details = extract_json_ld_data(soup)
    
    if not details.get("name"):
        h1 = soup.find("h1")
        details["name"] = h1.get_text(strip=True) if h1 else "Unknown"

    # Only click 'show number' if we didn't already get the phone number via JSON
    if not details.get("phone"):
        click_if_present(
            driver,
            "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show number')]",
            pause=1.0,
        )

    scroll_until_stable(driver, max_rounds=6)

    details["menu"] = extract_menu(driver)
    return details


# ==========================================
# DOWNLOAD + UPLOAD
# ==========================================
def download_images(scraped_categories: Dict[str, List[str]], restaurant_name: str):
    downloaded_paths, downloaded_categories = [], []
    cat_counts = {"Food": 0, "Ambience": 0, "By User": 0, "Drink": 0, "General": 0}
    safe_name = safe_filename(restaurant_name)

    for cat in ["Food", "Ambience", "By User", "Drink"]:
        for url in scraped_categories.get(cat, [])[:MAX_IMAGES_PER_CATEGORY]:
            cat_counts[cat] += 1
            try:
                img_res = SESSION.get(url, timeout=(10, 20))
                if img_res.status_code == 200 and img_res.content:
                    path = os.path.join(LOCAL_IMAGE_FOLDER, f"{safe_name}_{cat}_{cat_counts[cat]}.jpg")
                    with open(path, "wb") as f:
                        f.write(img_res.content)
                    downloaded_paths.append(path)
                    downloaded_categories.append(cat)
            except requests.RequestException:
                continue

    remaining = MAX_TOTAL_IMAGES - len(downloaded_paths)
    if remaining > 0:
        for url in scraped_categories.get("All", [])[:remaining]:
            cat_counts["General"] += 1
            try:
                img_res = SESSION.get(url, timeout=(10, 20))
                if img_res.status_code == 200 and img_res.content:
                    path = os.path.join(LOCAL_IMAGE_FOLDER, f"{safe_name}_General_{cat_counts['General']}.jpg")
                    with open(path, "wb") as f:
                        f.write(img_res.content)
                    downloaded_paths.append(path)
                    downloaded_categories.append("General")
            except requests.RequestException:
                continue

    return downloaded_paths, downloaded_categories

def upload_restaurant(restaurant_url, details, downloaded_paths, downloaded_categories, district="", state="") -> bool:
    data = {
        "name": details.get("name", "") or "",
        "phone": details.get("phone", "") or "",
        "whatsapp": details.get("whatsapp", "") or "",
        "address": details.get("address", "") or "",
        "opening_hours": details.get("opening_hours", "") or "",
        "source_url": restaurant_url,
        "district": district or details.get("district", "") or "",
        "state": state or details.get("state", "") or "",
        "menu_json": json.dumps(details.get("menu", []), ensure_ascii=False),
        "amenities_json": json.dumps(details.get("amenities", {}), ensure_ascii=False),
        "image_categories": json.dumps(downloaded_categories, ensure_ascii=False),
    }
    try:
        with ExitStack() as stack:
            files = [
                ("images", (os.path.basename(p), stack.enter_context(open(p, "rb")), "image/jpeg"))
                for p in downloaded_paths
            ]
            response = SESSION.post(API_UPLOAD_URL, files=files or None, data=data, timeout=(15, 60))
            if response.status_code in (200, 201):
                return True
            log(f"   ❌ Upload failed: {response.status_code} | {response.text[:300]}")
            return False
    except requests.RequestException as e:
        log(f"   ❌ Upload request failed: {e}")
        return False


# ==========================================
# ORCHESTRATOR
# ==========================================
def scrape_district(driver, base_url: str):
    log(f"\n🌍 Starting scrape for: {base_url}")
    all_urls = get_all_paginated_urls(driver, base_url)
    log(f"\n🎯 Total unique restaurants found: {len(all_urls)}")
    if not all_urls:
        return

    success_count = 0
    for index, restaurant_url in enumerate(all_urls, start=1):
        log("\n" + "-" * 50)
        log(f"🏪 [{index}/{len(all_urls)}] Processing: {restaurant_url}")
        try:
            details = scrape_restaurant_details(driver, restaurant_url)
            log(f"   📝 Name: {details.get('name', 'Unknown')}")
            log(f"   📞 Phone: {details.get('phone', 'N/A')}")
            log(f"   💬 WA: {details.get('whatsapp', 'N/A')}")
            log(f"   📋 Menu Items: {len(details.get('menu', []))}")

            scraped_categories = scrape_gallery_images(driver, restaurant_url)
            downloaded_paths, downloaded_categories = download_images(scraped_categories, details.get("name", "Unknown"))

            log("   ☁️ Uploading to API...")
            if upload_restaurant(restaurant_url, details, downloaded_paths, downloaded_categories):
                log("   ✅ Successfully uploaded!")
                success_count += 1
        except Exception as e:
            log(f"   ⚠️ Error processing {restaurant_url}: {e}")
            continue

    log(f"\n🏁 Finished district. Uploaded {success_count}/{len(all_urls)} restaurants.")


# ==========================================
# BROWSER + MAIN
# ==========================================
def build_driver(browser_type="chrome"):
    if browser_type == "edge":
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        
        options = EdgeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=en-US")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        if HEADLESS:
            options.add_argument("--headless")
            options.add_argument("--window-size=1920,1080")
            
        if USE_PROFILE:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
            profile_path = os.path.join(project_root, "scraper_edge_profile")
            os.makedirs(profile_path, exist_ok=True)
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument(f"--profile-directory={PROFILE_DIR_NAME}")
            
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

    if HEADLESS:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")

    # Use persistent chrome_user_data — keeps JustDial session/cookies
    # This is what allows detail pages (_BZDET) to load without being blocked
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    chrome_user_data = os.path.join(project_root, "chrome_user_data")
    chrome_drivers_dir = os.path.join(project_root, "chrome_drivers")
    os.makedirs(chrome_user_data, exist_ok=True)
    os.makedirs(chrome_drivers_dir, exist_ok=True)

    def _make_chrome_options():
        opts = uc.ChromeOptions()
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-notifications")
        opts.add_argument("--lang=en-US")
        if HEADLESS:
            opts.add_argument("--headless=new")
            opts.add_argument("--window-size=1920,1080")
        opts.add_argument(f"--user-data-dir={chrome_user_data}")
        if USE_PROFILE:
            opts.add_argument(f"--profile-directory={PROFILE_DIR_NAME}")
        return opts

    # Try version_main=149 first (matches your Chrome 149)
    try:
        return uc.Chrome(options=_make_chrome_options(), version_main=149,
                         patcher_kwargs={"target_dir": chrome_drivers_dir})
    except Exception as e:
        log(f"⚠️ uc.Chrome version_main=149 failed: {e}. Trying autodetect...")
    try:
        return uc.Chrome(options=_make_chrome_options(), patcher_kwargs={"target_dir": chrome_drivers_dir})
    except Exception as e2:
        log(f"❌ uc.Chrome failed: {e2}. Falling back to standard Chrome...")
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        std_opts = ChromeOptions()
        std_opts.add_argument("--start-maximized")
        std_opts.add_argument(f"--user-data-dir={chrome_user_data}")
        return webdriver.Chrome(options=std_opts)


def scrape_and_upload():
    log("🚀 INIT: Starting Multi-District Master Scraper...")
    try:
        driver = build_driver()
    except Exception as e:
        log(f"❌ Failed to start browser: {e}")
        return

    try:
        if MANUAL_CAPTCHA and not HEADLESS:
            log("\n" + "=" * 60)
            log("⚠️ CHECK THE CHROME BROWSER WINDOW!")
            log("Solve any CAPTCHA, then press ENTER here to continue...")
            log("=" * 60)
            try:
                input()
            except EOFError:
                log("⚠️ Non-interactive mode. Skipping manual CAPTCHA pause.")

        for base_url in TARGET_DISTRICTS:
            scrape_district(driver, base_url)
            log("⏳ Taking a 5-second breather before next district...")
            time.sleep(5)

    except KeyboardInterrupt:
        log("\n🛑 Interrupted by user.")
    except Exception as e:
        log(f"🔥 Fatal Error: {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        log("\n🏆 ALL DISTRICTS COMPLETED!")


def scrape_city(district: str, main_cat: str, subcat: str, max_limit=10, fast_mode=False, start_page=1, browser_type="chrome"):
    base_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{subcat.replace(' ', '-')}"
    if subcat == "All" or not subcat.strip():
        base_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{main_cat.replace(' ', '-')}"

    # ---- Detect if user passed a direct detail page URL (e.g. _BZDET) ----
    if "_BZDET" in base_url or "_BZDET" in district:
        actual_url = district if district.startswith("http") else base_url
        log(f"Detected detail page URL — switching to single URL scrape: {actual_url}")
        scrape_single_url(actual_url, browser_type=browser_type)
        return
        
    log(f"Selenium Engine ({browser_type}) Starting Scrape: {base_url}")
    
    try:
        driver = build_driver(browser_type=browser_type)
    except Exception as e:
        log(f"❌ Failed to start browser: {e}")
        return

    try:
        log(f"Resolving canonical URL for {base_url}...")
        safe_get(driver, base_url)
        resolved_base_url = base_url
        for _ in range(15):
            if 'nct-' in driver.current_url:
                resolved_base_url = driver.current_url.split('?')[0].rstrip('/')
                break
            time.sleep(1)
            
        log(f"Resolved canonical URL: {resolved_base_url}")
        
        max_count = float('inf') if max_limit == "All" else int(max_limit)
        scraped_count = 0
        
        page_num = start_page
        while scraped_count < max_count:
            current_url = resolved_base_url if page_num == 1 else f"{resolved_base_url}/page-{page_num}"
            log(f"📄 Fetching page {page_num}: {current_url}")
            try:
                if page_num > start_page:
                    safe_get(driver, current_url)
                scroll_until_stable(driver, max_rounds=6)
            except Exception as e:
                log(f"⚠️ Failed page {page_num}: {e}")
                break

            # ---- Get _BZDET detail URLs from search page ----
            page_urls = extract_links_from_page(driver)

            if not page_urls:
                log("No items found on this page, might have reached the end.")
                break

            log(f"Found {len(page_urls)} restaurant URLs on page {page_num}.")

            for url in page_urls:
                if scraped_count >= max_count:
                    break

                log("\n" + "-" * 50)
                log(f"🏪 [{scraped_count + 1}/{max_count}] Processing: {url}")
                try:
                    details = scrape_restaurant_details(driver, url)
                    log(f"   📝 Name: {details.get('name', 'Unknown')}")
                    log(f"   📞 Phone: {details.get('phone', 'N/A')}")

                    if not details or not details.get("name") or details.get("name") == "Unknown":
                        log("   ⚠️ Blocked or failed to get details, skipping.")
                        continue

                    scraped_categories = scrape_gallery_images(driver, url)
                    downloaded_paths, downloaded_categories = download_images(scraped_categories, details.get("name", "Unknown"))

                    log("   ☁️ Uploading to API...")
                    if upload_restaurant(url, details, downloaded_paths, downloaded_categories, district=district):
                        log("   ✅ Successfully uploaded!")
                        scraped_count += 1
                    else:
                        log("   ❌ Upload failed.")
                except Exception as e:
                    log(f"   ⚠️ Error processing {url}: {e}")

            page_num += 1
            
    except Exception as e:
        log(f"🔥 Fatal Error: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass
        log(f"\n🏆 Finished Selenium scrape. Scraped {scraped_count} restaurants.")


def scrape_single_url(url: str, engine: str = "playwright", browser_type="chrome"):
    log(f"Running single URL scrape with desktop scraper: {url} using {browser_type}")
    try:
        driver = build_driver(browser_type=browser_type)
        details = scrape_restaurant_details(driver, url)
        if not details or details.get("name", "Unknown") == "Unknown":
            log("Failed to extract details or blocked by CAPTCHA.")
            return False
        scraped_categories = scrape_gallery_images(driver, url)
        downloaded_paths, downloaded_categories = download_images(scraped_categories, details["name"])
        res = upload_restaurant(url, details, downloaded_paths, downloaded_categories)
        return res
    except Exception as e:
        log(f"Error in single scrape: {e}")
        return False
    finally:
        try:
            driver.quit()
        except:
            pass
if __name__ == "__main__":
    scrape_and_upload()