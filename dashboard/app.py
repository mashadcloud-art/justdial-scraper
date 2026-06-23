import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import math

API_URL = "http://localhost:8000/api/v1"

st.set_page_config(page_title="JustDial Master Dashboard", page_icon="🍽️", layout="wide")
st.title("️ JustDial Master Dashboard")

# --- SECTION 1: YOUR SCRAPED DATABASE STATS ---
st.header("📊 Your Scraped Database Stats")
try:
    stats_res = requests.get(f"{API_URL}/stats", timeout=2)
    if stats_res.status_code == 200:
        stats = stats_res.json()
        c1, c2, c3 = st.columns(3)
        c1.metric("🏪 Total Scraped Listings", stats.get('total_listings', stats.get('total_restaurants', 0)))
        c2.metric("🖼️ Total Scraped Images", stats.get('total_images', 0))
        c3.metric("️ Total Scraped Menu Items", stats.get('total_menu_items', 0))
    else:
        st.warning("API is not running. Please start your API with `python -m app.main`")
except Exception as e:
    st.error(f"Could not connect to API: {e}")

st.divider()

# --- SECTION 2: LIVE JUSTDIAL SOURCE STATS (NEW!) ---
st.header("🌐 Live JustDial Source Stats")
st.markdown("Enter a JustDial search URL to see the **Total Listings** and **All Categories** available on the website.")

search_url = st.text_input("JustDial Search URL:", "https://www.justdial.com/Kasaragod/Restaurants/nct-10408936")

if st.button("🔍 Fetch JustDial Stats"):
    with st.spinner("Fetching data from JustDial..."):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(search_url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the hidden __NEXT_DATA__ script tag
            script = soup.find('script', id='__NEXT_DATA__')
            
            if script:
                data = json.loads(script.string)
                props = data.get('props', {}).get('pageProps', {})
                
                # 1. Extract Total Listings
                total_listings = props.get('results', {}).get('totalNumberofResults', '0')
                total_pages = math.ceil(int(total_listings) / 10) if total_listings else 0
                
                st.success(f"Successfully fetched data!")
                
                col1, col2 = st.columns(2)
                col1.metric("📋 Total Listings on JustDial", total_listings)
                col2.metric("📄 Total Pages (approx)", total_pages)
                
                # 2. Extract All Categories from 'hotky'
                st.subheader(" Available Categories & Sub-categories")
                hotky_data = props.get('hotky', {}).get('data', [])
                
                categories_found = False
                for section in hotky_data:
                    # Look for the section containing categories (usually titled "Popular Categories" or similar)
                    if section.get('title') == 'Popular Categories' or section.get('htitle') == 'Popular Categories':
                        cat_groups = section.get('data', {})
                        
                        # Create tabs for each category group (e.g., "Food", "Hotels", "Services")
                        if cat_groups:
                            tab_names = list(cat_groups.keys())
                            tabs = st.tabs(tab_names)
                            
                            for i, group_name in enumerate(tab_names):
                                with tabs[i]:
                                    st.write(f"**{group_name}**")
                                    items = cat_groups[group_name]
                                    for item in items:
                                        name = item.get('name', '')
                                        link = item.get('link', '')
                                        if name and link:
                                            st.markdown(f"- [{name}]({link})")
                            categories_found = True
                            break # Stop after finding the main category block
                
                if not categories_found:
                    st.info("No specific category groups found in the standard format for this URL.")
                    
            else:
                st.error("Could not find page data. JustDial might be blocking the request or the URL is invalid.")
                
        except Exception as e:
            st.error(f"Error fetching data: {e}")

st.divider()

# --- SECTION 3: VIEW SCRAPED LISTINGS ---
st.header("🏪 View Your Scraped Listings")

col_search, col_refresh = st.columns([3, 1])
with col_search:
    search_query = st.text_input("🔍 Search by name, phone or address", "")
with col_refresh:
    st.write("")
    if st.button("🔄 Refresh"):
        st.rerun()

def get_all_listings():
    all_data = []
    page = 1
    limit = 100
    while True:
        try:
            res = requests.get(f"{API_URL}/listings", params={"page": page, "limit": limit}, timeout=10)
            if res.status_code != 200:
                break
            resp = res.json()
            if isinstance(resp, list):
                all_data.extend(resp)
                break
            batch = resp.get("data", [])
            all_data.extend(batch)
            total = resp.get("total_count", 0)
            if len(all_data) >= total or len(batch) < limit:
                break
            page += 1
        except Exception as e:
            st.error(f"Error fetching page {page}: {e}")
            break
    return all_data

try:
    all_listings = get_all_listings()
    # Filter by search
    if search_query:
        q = search_query.lower()
        all_listings = [r for r in all_listings if
            q in (r.get('name') or '').lower() or
            q in (r.get('phone') or '').lower() or
            q in (r.get('address') or '').lower()]

    st.write(f"Showing **{len(all_listings)}** listings")

    for r in all_listings:
            with st.container(border=True):
                col1, col2 = st.columns([1, 3])
                with col1:
                    if r.get('image_path'):
                        st.image(f"http://localhost:8000/{r['image_path']}", width=200)
                with col2:
                    st.subheader(r['name'])
                    if r.get('phone'): st.markdown(f"📞 **Phone:** {r['phone']}")
                    if r.get('whatsapp'): st.markdown(f"💬 **WhatsApp:** {r['whatsapp']}")
                    if r.get('address'): st.markdown(f"📍 **Address:** {r['address']}")
                    if r.get('opening_hours'): st.markdown(f" **Hours:** {r['opening_hours']}")
                    
                    if r.get('menu_items'):
                        with st.expander(f"🍽️ View Menu ({len(r['menu_items'])} items)"):
                            for item in r['menu_items'][:20]:
                                veg_icon = "" if item['is_veg'] else "🔴"
                                st.markdown(f"{veg_icon} **{item['name']}** - ₹{item['price']}")
except Exception as e:
    st.error(f"Error loading listings: {e}")