"""
Streamlit UI for the Google Maps High-Res Image Scraper
=======================================================
"""

import streamlit as st
import os
import re
from playwright.sync_api import sync_playwright
import httpx
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Page config
st.set_page_config(
    page_title="Google Maps Image Scraper",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar
st.sidebar.title("⚙️ Scraper Settings")
max_images = st.sidebar.number_input(
    "Max Images per Place",
    min_value=1,
    max_value=500,
    value=100,
    step=10,
)

# Main page
st.title("🗺️ Google Maps High-Resolution Image Scraper")
st.markdown(
    "Scrape high-res images from Google Maps places! Choose an input method below:"
)

# Input tabs
tab1, tab2, tab3 = st.tabs(
    ["📝 Search Query", "📄 Place Names File", "🔗 Google Maps URLs File"]
)

# Tab 1: Search Query
with tab1:
    st.subheader("Search for Places by Query")
    search_query = st.text_input("Enter your search query (e.g., 'restaurants in kochi')")
    max_places_per_search = st.number_input(
        "Max places to find per search",
        min_value=1,
        max_value=200,
        value=20,
        step=5,
    )

# Tab 2: Place Names File
with tab2:
    st.subheader("Use a File of Place Names")
    place_names_file = st.file_uploader(
        "Upload a text file with ONE PLACE NAME PER LINE",
        type=["txt"],
    )

# Tab 3: URLs File
with tab3:
    st.subheader("Use a File of Google Maps URLs")
    urls_file = st.file_uploader(
        "Upload a text file with ONE GOOGLE MAPS URL PER LINE",
        type=["txt"],
    )

# Other options
st.markdown("---")
col1, col2 = st.columns([1, 1])
with col1:
    no_downloads = st.checkbox(
        "Only save image links (don't download images)",
        value=False,
        help="Check this if you just want the image URLs, not the actual image files",
    )
with col2:
    output_dir = st.text_input(
        "Output directory name",
        value="scraper_results",
        help="Name of the folder where results will be saved",
    )

# Helper functions (synchronous versions)
def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:100]

def to_high_res_url(img_url: str) -> str:
    if not img_url or "googleusercontent" not in img_url:
        return img_url
    cleaned_url = re.sub(r"=\w+-\w+.*$", "", img_url)
    return cleaned_url + "=w4096-h4096-k-no"

def search_for_place_and_get_url(page, place_name: str) -> str:
    try:
        search_url = f"https://www.google.com/maps/search/{place_name.replace(' ', '+')}?hl=en"
        page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2000)
        if "/maps/place/" in page.url or "/place/" in page.url:
            return page.url
        panel_selector = "div[role='feed']"
        for _ in range(3):
            page.evaluate('document.querySelector("div[role=\'feed\']")?.scrollBy(0,1200)')
            page.wait_for_timeout(600)
        feed_el = page.query_selector(panel_selector)
        if feed_el:
            first_link = feed_el.query_selector("a[href*='/maps/place/']")
            if first_link:
                href = first_link.get_attribute("href")
                return href
        return ""
    except Exception as e:
        return ""

def scrape_place_highres_images(page, place_url: str, max_img: int) -> Dict:
    result = {
        "place_url": place_url,
        "place_name": f"place_{hash(place_url)}",
        "image_urls": []
    }
    try:
        page.goto(place_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)
        name_el = page.query_selector("h1.DUwDvf, h1[class*='fontHeadlineLarge']")
        if name_el:
            result["place_name"] = name_el.inner_text()
        seen_bases = set()
        main_imgs = page.evaluate("""() => Array.from(document.querySelectorAll('img'))
            .map(img => img.src)
            .filter(src => {
                if (!src || !src.includes('googleusercontent')) return false;
                if (src.includes('w32-h32') || src.includes('w48-h48') || src.includes('w64-h64')) return false;
                if (src.includes('/a/') || src.includes('/a-/')) return false;
                return true;
            })""")
        for img_url in main_imgs:
            base_url = re.sub(r"=\w+-\w+.*$", "", img_url)
            if base_url not in seen_bases:
                seen_bases.add(base_url)
                result["image_urls"].append(to_high_res_url(img_url))
                if len(result["image_urls"]) >= max_img:
                    break
        if len(result["image_urls"]) < max_img:
            photo_btns = [
                "button[jsaction*='pane.heroHeaderImage.photos']",
                "div.YkuOqf button",
                "button[aria-label*='photo' i]",
                "button[aria-label*='Photos' i]",
                "button[jsaction*='photos']",
                "button[jsaction*='heroHeaderImage']",
                "div[class*='gallery'] button",
                "button[class*='ao3bfe']"
            ]
            clicked = False
            for sel in photo_btns:
                btn = page.query_selector(sel)
                if btn:
                    try:
                        btn.click(timeout=5000)
                        page.wait_for_timeout(2500)
                        clicked = True
                        break
                    except:
                        continue
            if clicked:
                try:
                    for tab_label in ["By owner", "Owner", "Exterior", "Interior"]:
                        tab_btn = page.get_by_role("button", name=tab_label, exact=False).first
                        if tab_btn.is_visible():
                            tab_btn.click()
                            page.wait_for_timeout(2000)
                            break
                except:
                    pass
                scroll_attempts = 0
                no_new = 0
                while scroll_attempts < 80 and no_new < 8 and len(result["image_urls"]) < max_img:
                    current_imgs = page.evaluate("""() => Array.from(document.querySelectorAll('img'))
                        .map(img => img.src)
                        .filter(src => {
                            if (!src || !src.includes('googleusercontent')) return false;
                            if (src.includes('w32-h32') || src.includes('w48-h48') || src.includes('w64-h64')) return false;
                            if (src.includes('/a/') || src.includes('/a-/')) return false;
                            return true;
                        })""")
                    new_found = 0
                    for img_url in current_imgs:
                        base_url = re.sub(r"=\w+-\w+.*$", "", img_url)
                        if base_url not in seen_bases:
                            seen_bases.add(base_url)
                            result["image_urls"].append(to_high_res_url(img_url))
                            new_found += 1
                            if len(result["image_urls"]) >= max_img:
                                break
                    if new_found == 0:
                        no_new += 1
                    else:
                        no_new = 0
                    page.evaluate("""document.querySelectorAll('div.m6QErb, div[role=main], div[role=feed], div[class*="gallery"], div[class*="scroll"], div[jsname], div[data-logged], div[class*="DdKZJb"]')
                        .forEach(function(el) { el.scrollBy(0, 5000); })""")
                    page.wait_for_timeout(1000)
                    scroll_attempts += 1
    except Exception as e:
        pass
    return result

def save_image_links_to_files(all_data: List[Dict], output_path: str):
    os.makedirs(output_path, exist_ok=True)
    import json
    import csv
    json_path = os.path.join(output_path, "scraped_image_links.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    csv_path = os.path.join(output_path, "scraped_image_links.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["place_name", "place_url", "image_index", "image_url"])
        for pd in all_data:
            for idx, img in enumerate(pd["image_urls"]):
                writer.writerow([pd["place_name"], pd["place_url"], idx+1, img])

def download_single_image(img_url, img_path):
    try:
        resp = httpx.get(img_url, timeout=120, follow_redirects=True)
        if resp.status_code == 200:
            with open(img_path, "wb") as f:
                f.write(resp.content)
            return True
    except:
        pass
    return False

# Main scraping function
def run_scraper():
    output_path = os.path.abspath(output_dir)
    os.makedirs(output_path, exist_ok=True)
    st.info(f"📂 Output will be saved to: {output_path}")
    place_urls = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        if search_query:
            st.subheader("🔍 Searching for places...")
            search_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}?hl=en"
            page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2000)
            if "/maps/place/" in page.url or "/place/" in page.url:
                place_urls.append(page.url)
            else:
                for _ in range(8):
                    page.evaluate('document.querySelector("div[role=\'feed\']")?.scrollBy(0,1200)')
                    page.wait_for_timeout(600)
                feed_el = page.query_selector("div[role='feed']")
                if feed_el:
                    listings = feed_el.query_selector_all("a[href*='/maps/place/']")
                    for link in listings:
                        href = link.get_attribute("href")
                        if href and href not in place_urls:
                            place_urls.append(href)
                            if len(place_urls) >= max_places_per_search:
                                break
        elif place_names_file:
            st.subheader("📄 Processing place names file...")
            temp_path = os.path.join(output_path, "temp_names.txt")
            with open(temp_path, "wb") as f:
                f.write(place_names_file.getvalue())
            with open(temp_path, "r", encoding="utf-8") as f:
                for line in f:
                    name = line.strip()
                    if name and not name.startswith("#"):
                        url = search_for_place_and_get_url(page, name)
                        if url:
                            place_urls.append(url)
            os.remove(temp_path)
        elif urls_file:
            st.subheader("🔗 Processing Google Maps URLs file...")
            temp_path = os.path.join(output_path, "temp_urls.txt")
            with open(temp_path, "wb") as f:
                f.write(urls_file.getvalue())
            with open(temp_path, "r", encoding="utf-8") as f:
                for line in f:
                    url = line.strip()
                    if url and url.startswith("http") and not url.startswith("#"):
                        place_urls.append(url)
            os.remove(temp_path)
        browser.close()
    if not place_urls:
        st.error("❌ No places found! Please check your input.")
        return
    st.success(f"✅ Found {len(place_urls)} places to scrape!")
    all_place_data = []
    st.subheader("🖼️ Scraping images...")
    progress = st.progress(0, "Starting to scrape places...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        for i, purl in enumerate(place_urls):
            progress.progress(i / len(place_urls), f"Scraping place {i+1}/{len(place_urls)}...")
            pd = scrape_place_highres_images(page, purl, max_images)
            if pd["image_urls"]:
                all_place_data.append(pd)
        browser.close()
    progress.progress(1.0, "Scraping complete!")
    if all_place_data:
        total = sum(len(x["image_urls"]) for x in all_place_data)
        st.success(f"✅ Scraped {total} image links from {len(all_place_data)} places!")
        save_image_links_to_files(all_place_data, output_path)
        if not no_downloads:
            all_tasks = []
            for pd in all_place_data:
                pdir = sanitize_filename(pd["place_name"])
                ppath = os.path.join(output_path, pdir)
                os.makedirs(ppath, exist_ok=True)
                for j, img_url in enumerate(pd["image_urls"]):
                    fname = f"{pdir}_img_{j+1}.jpg"
                    fpath = os.path.join(ppath, fname)
                    all_tasks.append((img_url, fpath))
            if all_tasks:
                st.subheader("📥 Downloading images...")
                dl_progress = st.progress(0, f"Downloading {len(all_tasks)} images...")
                successful = 0
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = {executor.submit(download_single_image, url, path): (url, path) for url, path in all_tasks}
                    for i, future in enumerate(as_completed(futures)):
                        if future.result():
                            successful += 1
                        dl_progress.progress((i+1)/len(all_tasks), f"Downloaded {i+1}/{len(all_tasks)} images...")
                dl_progress.progress(1.0, f"Download complete! {successful}/{len(all_tasks)} successful!")
                st.success(f"✅ Downloaded {successful}/{len(all_tasks)} images!")
        st.markdown("---")
        st.subheader("📊 Results Summary")
        for pd in all_place_data:
            st.write(f"- **{pd['place_name']}**: {len(pd['image_urls'])} images")
        st.balloons()
    else:
        st.error("❌ No images found!")

# Run button
st.markdown("---")
if st.button("🚀 Start Scraping", type="primary", use_container_width=True):
    run_scraper()
