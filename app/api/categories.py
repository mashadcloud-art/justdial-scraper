from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
import json
import time
import re
import threading
import os

from app.database import get_db
from app import models

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])

# ─── In-memory cache for listing counts ─────────────────
_count_cache: dict = {}  # key: "city|category|subcategory" -> {"count": int|str, "ts": float}
_CACHE_TTL = 3600  # 1 hour
_cache_lock = threading.Lock()

def _cache_key(city: str, category: str, subcategory: Optional[str]) -> str:
    return f"{city}|{category}|{subcategory or ''}"

def _get_cached(key: str):
    with _cache_lock:
        entry = _count_cache.get(key)
        if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
            return entry["count"]
    return None

def _set_cached(key: str, count):
    with _cache_lock:
        _count_cache[key] = {"count": count, "ts": time.time()}


def _extract_count_from_html(html_text: str, category: str, subcategory: Optional[str]) -> Optional[int]:
    """Extract listing count from HTML using multiple patterns"""
    soup = BeautifulSoup(html_text, 'html.parser')
    page_text = soup.get_text()

    # Try multiple patterns to extract listing count
    patterns = [
        r'(\d[\d,]+)\+?\s*[Ll]istings?',                # "345+ Listings" or "345 Listings"
        r'[Ss]howing\s+\d+\s*[-–]\s*\d+\s+of\s+(\d[\d,]+)',  # "Showing 1 - 20 of 345"
        r'(\d[\d,]+)\s+results?\s+found',                # "345 results found"
        r'Total\s*:\s*(\d[\d,]+)',                        # "Total: 345"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, page_text)
        if match:
            count_str = match.group(1).replace(",", "")
            return int(count_str)

    # Check __NEXT_DATA__ JSON
    next_data_tag = soup.find('script', id='__NEXT_DATA__')
    if next_data_tag and next_data_tag.string:
        try:
            next_data = json.loads(next_data_tag.string)
            props = next_data.get('props', {}).get('pageProps', {})
            for k in ['totalCount', 'total', 'count', 'totResults', 'resultsCount', 'totalNumberofResults']:
                if k in props and props[k]:
                    return int(props[k])
            results = props.get('results', {})
            if isinstance(results, dict):
                for k in ['totalCount', 'total', 'totalNumberofResults']:
                    if k in results and results[k]:
                        return int(results[k])
        except (json.JSONDecodeError, ValueError, AttributeError):
            pass
    
    # Check JSON-LD structured data (BreadcrumbList)
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    for script in json_ld_scripts:
        if script.string and 'BreadcrumbList' in script.string and 'Listings' in script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'BreadcrumbList':
                    for item in data.get('itemListElement', []):
                        name = item.get('item', {}).get('name', '')
                        if 'Listings' in name:
                            match = re.search(r'(\d[\d,]+)\+', name)
                            if match:
                                return int(match.group(1).replace(",", ""))
            except (json.JSONDecodeError, ValueError, AttributeError):
                continue
                
    # Check meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        match = re.search(r'from\s+(\d[\d,]+)\s+Restaurants', meta_desc.get('content'), re.IGNORECASE)
        if match:
            return int(match.group(1).replace(",", ""))

    # Check title tag
    title = soup.find('title')
    if title:
        title_match = re.search(
            r'(\d[\d,]+)\+?\s*(?:Best|Top)?\s*' + re.escape(subcategory or category),
            title.get_text(), re.IGNORECASE
        )
        if title_match:
            return int(title_match.group(1).replace(",", ""))
    
    return None


def _fetch_count_via_requests(search_url: str, category: str, subcategory: Optional[str]) -> Optional[int]:
    """Try to fetch count using plain HTTP requests (fast but may be blocked)"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.justdial.com/'
    }
    try:
        response = requests.get(search_url, headers=headers, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            return _extract_count_from_html(response.text, category, subcategory)
    except Exception:
        pass
    return None


def _fetch_count_via_selenium(search_url: str, category: str, subcategory: Optional[str]) -> Optional[int]:
    """Fetch count using headless Chrome (slower but bypasses blocks)"""
    try:
        import undetected_chromedriver as uc
        
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        driver_dir = os.path.join(project_root, "chrome_drivers")
        
        options = uc.ChromeOptions()
        # options.add_argument("--headless=new") # Disabled to avoid Justdial bot block
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # options.add_argument("--disable-gpu")
        
        driver = None
        try:
            try:
                driver = uc.Chrome(options=options, version_main=149, patcher_kwargs={"target_dir": driver_dir})
            except Exception as e:
                print(f"⚠️ uc.Chrome with version_main=149 failed in selenium-count: {e}. Trying autodetect...")
                try:
                    driver = uc.Chrome(options=options, patcher_kwargs={"target_dir": driver_dir})
                except Exception as e2:
                    print(f"❌ uc.Chrome autodetect failed: {e2}. Falling back to standard Chrome...")
                    from selenium import webdriver
                    driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(30)
            driver.get(search_url)
            time.sleep(5)  # Wait for JS to render
            
            html = driver.page_source
            count = _extract_count_from_html(html, category, subcategory)
            return count
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
    except Exception as e:
        print(f"Selenium count fetch failed: {e}")
        return None


@router.get("/count")
def get_category_count(city: str, category: str, subcategory: Optional[str] = None):
    """
    Get the quantity of listings for a category in a specific city from JustDial.
    Uses caching + requests fallback to Selenium headless.
    """
    from app.scraper.category_fetcher import build_search_url
    search_url = build_search_url(city, category, subcategory)
    cache_key = _cache_key(city, category, subcategory)
    
    # 1. Check cache first
    cached = _get_cached(cache_key)
    if cached is not None:
        return {"count": cached, "url": search_url, "cached": True}

    # 2. Try requests first (fast)
    count = _fetch_count_via_requests(search_url, category, subcategory)
    if count is not None:
        _set_cached(cache_key, count)
        return {"count": count, "url": search_url}

    # 3. Fallback to Selenium headless
    count = _fetch_count_via_selenium(search_url, category, subcategory)
    if count is not None:
        _set_cached(cache_key, count)
        return {"count": count, "url": search_url}

    # 4. Return "-" if all methods fail
    return {"count": "-", "url": search_url}


@router.get("/count/batch")
def get_category_counts_batch(city: str, categories: str):
    """
    Get listing counts for multiple categories at once.
    categories: comma-separated list of category names
    """
    from app.scraper.category_fetcher import build_search_url
    
    cat_list = [c.strip() for c in categories.split(",") if c.strip()]
    results = {}
    
    for cat in cat_list:
        cache_key = _cache_key(city, cat, None)
        cached = _get_cached(cache_key)
        if cached is not None:
            results[cat] = cached
        else:
            search_url = build_search_url(city, cat, None)
            count = _fetch_count_via_requests(search_url, cat, None)
            if count is not None:
                _set_cached(cache_key, count)
                results[cat] = count
            else:
                results[cat] = "-"
    
    return {"counts": results}

@router.get("/fetch-from-justdial")
def fetch_justdial_categories(city: str = "Mumbai", db: Session = Depends(get_db)):
    """
    Fetch all categories from JustDial homepage and save to database
    """
    try:
        # Clear old categories
        db.query(models.Category).delete()
        db.commit()
        
        # Fetch JustDial homepage
        url = f"https://www.justdial.com/{city}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        categories_added = 0
        
        # Look for category sections in the page
        # JustDial structures categories in various ways
        category_sections = soup.find_all(['div', 'section'], class_=lambda x: x and ('category' in x.lower() or 'popular' in x.lower()))
        
        for section in category_sections:
            links = section.find_all('a', href=True)
            for link in links:
                category_name = link.get_text(strip=True)
                category_url = link.get('href', '')
                
                if category_name and len(category_name) > 2 and category_url:
                    # Determine parent category from context
                    parent = "General"
                    if 'food' in category_name.lower() or 'restaurant' in category_url.lower():
                        parent = "Food & Restaurants"
                    elif 'hotel' in category_name.lower() or 'accommodation' in category_url.lower():
                        parent = "Accommodation"
                    elif 'doctor' in category_name.lower() or 'hospital' in category_url.lower():
                        parent = "Health & Medical"
                    elif 'school' in category_name.lower() or 'education' in category_url.lower():
                        parent = "Education"
                    
                    # Check if category already exists
                    existing = db.query(models.Category).filter(
                        models.Category.name == category_name
                    ).first()
                    
                    if not existing:
                        new_category = models.Category(
                            name=category_name,
                            parent_category=parent,
                            sub_category=None,
                            jd_url=category_url if category_url.startswith('http') else f"https://www.justdial.com{category_url}",
                            is_active=True
                        )
                        db.add(new_category)
                        categories_added += 1
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Fetched {categories_added} categories from JustDial",
            "total_categories": db.query(models.Category).count()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")

from pydantic import BaseModel

class ImportUrlRequest(BaseModel):
    url: str

def _fetch_html_page(url: str) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.justdial.com/'
    }
    
    html_content = ""
    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            html_content = response.text
    except Exception:
        pass
        
    # Playwright/Selenium Fallback
    if not html_content or "captcha" in html_content.lower() or "blocked" in html_content.lower() or "forbidden" in html_content.lower():
        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import stealth_sync
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                stealth_sync(page)
                page.goto(url, timeout=30000)
                time.sleep(3)
                html_content = page.content()
                browser.close()
        except Exception as pe:
            try:
                import undetected_chromedriver as uc
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                chrome_drivers_dir = os.path.join(project_root, "chrome_drivers")
                os.makedirs(chrome_drivers_dir, exist_ok=True)
                options = uc.ChromeOptions()
                options.add_argument("--headless=new")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--no-sandbox")
                try:
                    driver = uc.Chrome(options=options, version_main=149, patcher_kwargs={"target_dir": chrome_drivers_dir})
                except Exception as e:
                    print(f"⚠️ uc.Chrome with version_main=149 failed: {e}. Trying autodetect...")
                    try:
                        driver = uc.Chrome(options=options, patcher_kwargs={"target_dir": chrome_drivers_dir})
                    except Exception as e2:
                        print(f"❌ uc.Chrome autodetect failed: {e2}. Falling back to standard Chrome...")
                        from selenium import webdriver
                        driver = webdriver.Chrome(options=options)
                driver.set_page_load_timeout(30)
                driver.get(url)
                time.sleep(4)
                html_content = driver.page_source
                driver.quit()
            except Exception as se:
                print(f"Bypassing fail on subpage load: Playwright: {pe}. Selenium: {se}")
                
    return html_content

def _fetch_multiple_html_pages(urls: list[str]) -> list[str]:
    if not urls:
        return []
        
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.justdial.com/'
    }
    
    results = ["" for _ in range(len(urls))]
    
    # Try requests first
    for i, url in enumerate(urls):
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                results[i] = response.text
        except Exception:
            pass
            
    # For failed requests, use a single Playwright browser instance
    failed_indices = [i for i, html in enumerate(results) if not html or "captcha" in html.lower() or "blocked" in html.lower() or "forbidden" in html.lower()]
    if failed_indices:
        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import stealth_sync
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=headers['User-Agent'])
                page = context.new_page()
                stealth_sync(page)
                
                for idx in failed_indices:
                    url = urls[idx]
                    try:
                        page.goto(url, timeout=15000)
                        time.sleep(1)
                        results[idx] = page.content()
                    except Exception:
                        pass
                browser.close()
        except Exception as pe:
            print(f"Playwright batch load failed: {pe}")
            
    return results

def _parse_categories_from_html(html_content: str):
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, 'html.parser')
    subcategories = []
    
    # Extract city name suffix pattern (e.g. "Beds in Kutch", "Beds Near Kutch", etc.)
    city_pattern = r'\s+(?:in|near|near\s+by)\s+.*'
    
    anchors = soup.find_all('a', href=True)
    for anchor in anchors:
        href = anchor.get('href', '')
        text = anchor.get_text(strip=True)
        
        # If no text in the anchor, look inside children
        if not text:
            text_div = anchor.find(class_=re.compile(r'card\d+_text|card10_text'))
            if text_div:
                text = text_div.get_text(strip=True)
                
        # Clean text
        if text:
            text = text.replace('\n', ' ').strip()
            # Remove "in Kutch" / "near Kutch"
            text = re.sub(city_pattern, '', text, flags=re.IGNORECASE).strip()
            
        # Ignore external links, support, terms, ads, etc.
        if href.startswith('http') and 'justdial.com' not in href:
            continue
        if any(w in href.lower() for w in ['/advertise', '/free-listing', '/terms', '/privacy', '/feedback', '/social', '/support', '/blog']):
            continue
            
        is_category = False
        if 'fil-' in href or 'nct-' in href:
            is_category = True
        else:
            path_parts = [p for p in href.split('/') if p]
            # e.g., /Kutch/Furnitures
            if len(path_parts) == 2 and not path_parts[1].endswith('.html'):
                is_category = True
                
        if is_category and text and len(text) > 2:
            path_parts = [p for p in href.split('/') if p]
            if len(path_parts) >= 2:
                sub_key = path_parts[1]
                # Filter out general navigation terms
                if sub_key.lower() in ['login', 'register', 'home', 'kutch', 'kasaragod', 'mumbai', 'ahmedabad', 'thane', 'pune']:
                    continue
                subcategories.append({
                    "name": text,
                    "key": sub_key,
                    "url": href if href.startswith('http') else f"https://www.justdial.com{href}"
                })
                
    seen = set()
    unique_subs = []
    for s in subcategories:
        norm_name = s["name"].lower()
        if norm_name not in seen:
            seen.add(norm_name)
            unique_subs.append(s)
    return unique_subs

@router.post("/import-from-url")
def import_categories_from_url(request: ImportUrlRequest):
    """
    Scrape nested subcategories recursively (up to 3 levels deep) from a specific JustDial category page URL
    and return them as a hierarchical tree structure.
    """
    url = request.url
    html_content = _fetch_html_page(url)
    if not html_content:
        raise HTTPException(status_code=500, detail="Failed to load category page")
        
    soup = BeautifulSoup(html_content, 'html.parser')
    heading_tag = soup.find('h1')
    main_category = heading_tag.get_text(strip=True) if heading_tag else "Home Decor"
    
    # 1. Get first-level subcategories
    level1_subs = _parse_categories_from_html(html_content)
    
    category_tree = []
    
    # Fetch first-level subcategory pages in a batch
    level1_urls = [s1["url"] for s1 in level1_subs[:8]]
    level1_htmls = _fetch_multiple_html_pages(level1_urls)
    
    for i, s1 in enumerate(level1_subs[:8]):
        s1_html = level1_htmls[i] if i < len(level1_htmls) else ""
        children = []
        if s1_html:
            level2_subs = _parse_categories_from_html(s1_html)
            
            # Fetch level 3 pages for the first few level 2 items
            level2_urls = [s2["url"] for s2 in level2_subs[:5]]
            level2_htmls = _fetch_multiple_html_pages(level2_urls)
            
            for j, s2 in enumerate(level2_subs):
                children.append({"name": s2["name"], "key": s2["key"]})
                
                # Fetch deeper levels
                s2_html = level2_htmls[j] if j < len(level2_htmls) else ""
                if s2_html:
                    level3_subs = _parse_categories_from_html(s2_html)
                    for s3 in level3_subs:
                        children.append({"name": s3["name"], "key": s3["key"]})
                        
        # Deduplicate children
        seen_childs = set()
        unique_children = []
        for child in children:
            norm_c = child["name"].lower()
            if norm_c != s1["name"].lower() and norm_c not in seen_childs:
                seen_childs.add(norm_c)
                unique_children.append(child)
                
        category_tree.append({
            "name": s1["name"],
            "key": s1["key"],
            "url": s1["url"],
            "children": unique_children
        })
        
    return {
        "status": "success",
        "main_category": main_category,
        "tree": category_tree
    }

@router.get("/list")
def list_categories(
    parent: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all categories with optional filtering
    """
    query = db.query(models.Category).filter(models.Category.is_active == True)
    
    if parent:
        query = query.filter(models.Category.parent_category == parent)
    
    if search:
        query = query.filter(models.Category.name.ilike(f"%{search}%"))
    
    categories = query.order_by(models.Category.parent_category, models.Category.name).all()
    
    return {
        "total": len(categories),
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "parent": c.parent_category,
                "url": c.jd_url
            }
            for c in categories
        ]
    }

@router.post("/select")
def select_category_for_scraping(
    category_id: int,
    city: str,
    db: Session = Depends(get_db)
):
    """
    Select a category for scraping in a specific city
    """
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Check if already selected
    existing = db.query(models.SelectedCategory).filter(
        models.SelectedCategory.category_id == category_id,
        models.SelectedCategory.city == city
    ).first()
    
    if existing:
        return {"status": "already_selected", "message": "Category already selected for this city"}
    
    selection = models.SelectedCategory(
        category_id=category_id,
        city=city
    )
    db.add(selection)
    db.commit()
    
    return {"status": "success", "message": f"Selected {category.name} for scraping in {city}"}

@router.get("/selected")
def get_selected_categories(city: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get all selected categories for scraping
    """
    query = db.query(models.SelectedCategory).join(models.Category)
    
    if city:
        query = query.filter(models.SelectedCategory.city == city)
    
    selections = query.all()
    
    return {
        "total": len(selections),
        "selections": [
            {
                "id": s.id,
                "category": s.category.name,
                "parent": s.category.parent_category,
                "city": s.city,
                "url": s.category.jd_url,
                "selected_at": s.selected_at.isoformat()
            }
            for s in selections
        ]
    }

@router.delete("/selected/{selection_id}")
def deselect_category(selection_id: int, db: Session = Depends(get_db)):
    """
    Remove a category from selected list
    """
    selection = db.query(models.SelectedCategory).filter(
        models.SelectedCategory.id == selection_id
    ).first()
    
    if not selection:
        raise HTTPException(status_code=404, detail="Selection not found")
    
    db.delete(selection)
    db.commit()
    
    return {"status": "success", "message": "Category deselected"}