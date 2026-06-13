import streamlit as st
import requests
import time
import sys
import os
import subprocess
from datetime import datetime

# Add parent directory to path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = "http://localhost:8000/api/v1"
LOG_FILE = "scraper_logs.txt"

# Initialize session state
if 'is_scraping' not in st.session_state:
    st.session_state.is_scraping = False
if 'scraper_process' not in st.session_state:
    st.session_state.scraper_process = None

# ==========================================
# 1. PAGE SETUP
# ==========================================
st.set_page_config(page_title="JustDial Master Control", page_icon="🍽️", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
    .log-container { background-color: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 5px; max-height: 400px; overflow-y: auto; font-family: monospace; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

st.sidebar.title("JustDial Master")
page = st.sidebar.radio("Go to", [
    "Dashboard",
    "Category Management",
    "Scraper Control",
    "Database Management"
])

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def get_stats():
    try:
        res = requests.get(f"{API_URL}/stats", timeout=2)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return {"total_restaurants": 0, "total_images": 0, "total_menu_items": 0}

def clear_logs():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

def read_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    return ""

# ==========================================
# 3. MASSIVE INDIA STATE/CITY MAP
# ==========================================
STATE_CITIES = {
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Tirupati", "Rajahmundry", "Kakinada"],
    "Assam": ["Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon", "Tezpur"],
    "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Darbhanga", "Purnia"],
    "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg"],
    "Delhi NCR": ["New Delhi", "Noida", "Gurgaon", "Faridabad", "Ghaziabad"],
    "Goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar", "Gandhinagar"],
    "Haryana": ["Faridabad", "Gurgaon", "Panipat", "Ambala", "Hisar", "Karnal", "Rohtak"],
    "Himachal Pradesh": ["Shimla", "Mandi", "Dharamshala", "Solan", "Kangra"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Hazaribagh", "Deoghar"],
    "Karnataka": ["Bangalore", "Mysore", "Mangalore", "Hubli", "Belgaum", "Gulbarga", "Davangere", "Shimoga"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kollam", "Palakkad", "Alappuzha", "Kannur", "Kottayam"],
    "Madhya Pradesh": ["Indore", "Bhopal", "Jabalpur", "Gwalior", "Ujjain", "Sagar", "Dewas"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik", "Aurangabad", "Solapur", "Navi Mumbai"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur", "Puri"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda", "Mohali"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Bikaner", "Alwar"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tirunelveli", "Erode"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Agra", "Varanasi", "Meerut", "Prayagraj", "Noida", "Ghaziabad"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Roorkee", "Haldwani"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri", "Bardhaman"]
}

# ==========================================
# PAGE 1: DASHBOARD
# ==========================================
if page == "Dashboard":
    st.title("Restaurant Dashboard")
    stats = get_stats()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Restaurants", stats.get('total_restaurants', 0))
    c2.metric("Total Images", stats.get('total_images', 0))
    c3.metric("Total Menu Items", stats.get('total_menu_items', 0))

    st.divider()
    if st.button("Refresh Data"):
        st.rerun()

    try:
        response = requests.get(f"{API_URL}/restaurants", timeout=5)
        if response.status_code == 200:
            restaurants = response.json()
            if restaurants:
                for r in restaurants:
                    with st.container(border=True):
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            if r.get('image_path'):
                                st.image(f"http://localhost:8000/{r['image_path']}", width=300)
                        with col2:
                            st.subheader(r.get('name', 'Unknown'))
                            if r.get('phone'):
                                st.markdown(f"**Phone:** {r['phone']}")
                            if r.get('whatsapp'):
                                st.markdown(f"**WhatsApp:** {r['whatsapp']}")
                            if r.get('address'):
                                st.markdown(f"**Address:** {r['address']}")

                            if r.get('menu_items'):
                                with st.expander(f"View Menu ({len(r['menu_items'])} items)"):
                                    for item in r['menu_items'][:15]:
                                        veg_text = "Veg" if item.get('is_veg') else "Non-Veg"
                                        st.markdown(f"**{item.get('name', 'Unknown')}** - ₹{item.get('price', 'N/A')} ({veg_text})")
            else:
                st.info("No restaurants scraped yet! Go to 'Scraper Control' to start scraping.")
    except Exception as e:
        st.error(f"Could not connect to API. Is it running? Error: {e}")

# ==========================================
# PAGE 2: CATEGORY MANAGEMENT
# ==========================================
elif page == "Category Management":
    st.title("Category Management")
    st.markdown("Fetch, select, and manage JustDial categories for scraping")

    st.subheader("1. Fetch Categories from JustDial")
    if st.button("Fetch All Categories", type="primary"):
        with st.spinner("Fetching categories from JustDial..."):
            try:
                response = requests.get(f"{API_URL}/categories/fetch-from-justdial?city=Mumbai", timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"Success! {data.get('message', '')}")
                    st.info(f"Total categories in database: {data.get('total_categories', 0)}")
                else:
                    st.error(f"Failed to fetch categories: {response.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    st.subheader("2. Browse Categories")

    col1, col2 = st.columns(2)
    with col1:
        search_term = st.text_input("Search Categories", placeholder="e.g., Chinese, Hotel, Doctor")
    with col2:
        parent_filter = st.selectbox("Filter by Parent", ["All", "Food & Restaurants", "Health & Medical", "Education", "Accommodation", "Others"])

    try:
        params = {}
        if search_term:
            params['search'] = search_term
        if parent_filter != "All":
            params['parent'] = parent_filter

        response = requests.get(f"{API_URL}/categories/list", params=params, timeout=10)
        if response.status_code == 200:
            categories_data = response.json()
            st.write(f"Found **{categories_data.get('total', 0)}** categories")
            if categories_data.get('categories'):
                st.dataframe(categories_data['categories'], use_container_width=True, height=400)
    except Exception as e:
        st.error(f"Failed to load categories: {e}")

    st.divider()
    st.subheader("3. Select Categories for Scraping")

    col1, col2 = st.columns(2)
    with col1:
        category_id = st.number_input("Category ID", min_value=1, step=1)
    with col2:
        city = st.text_input("City", value="Mumbai", placeholder="e.g., Kochi, Delhi")

    if st.button("Select Category"):
        try:
            response = requests.post(
                f"{API_URL}/categories/select",
                params={"category_id": category_id, "city": city},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    st.success(f"Success! {data.get('message')}")
                else:
                    st.warning(data.get('message'))
            else:
                st.error(f"Failed: {response.status_code}")
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()
    st.subheader("4. Currently Selected Categories")

    try:
        response = requests.get(f"{API_URL}/categories/selected", timeout=10)
        if response.status_code == 200:
            selected_data = response.json()
            if selected_data.get('selections'):
                st.dataframe(selected_data['selections'], use_container_width=True, height=300)
            else:
                st.info("No categories selected yet. Use the form above to select categories.")
    except Exception as e:
        st.error(f"Failed to load selected categories: {e}")

# ==========================================
# PAGE 3: SCRAPER CONTROL
# ==========================================
elif page == "Scraper Control":
    st.title("Scraper Control")
    
    # Quick stats
    stats = get_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Restaurants", stats.get('total_restaurants', 0))
    c2.metric("Total Images", stats.get('total_images', 0))
    c3.metric("Total Menu Items", stats.get('total_menu_items', 0))
    
    st.divider()
    
    # Create tabs for different scraping modes
    tab_city, tab_url = st.tabs(["🏙️ City/District-Wise Scraping", "🔗 Manual URL Scraping"])
    
    # ------------------------------
    # Tab 1: City/District-Wise Scraping
    # ------------------------------
    with tab_city:
        st.subheader("Select District/City to Scrape")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_city = st.selectbox(
                "Select city/district",
                ["Kochi", "Thiruvananthapuram", "Kozhikode", "Thrissur", "Kollam", "Kannur", "Palakkad", "Alappuzha", "Kottayam", "Malappuram", "Thiruvalla", "Pathanamthitta"],
                index=0
            )
        
        with col2:
            max_limit = st.number_input("Max restaurants to scrape (0 for all)", min_value=0, value=2, step=1, key="city_limit")
        
        st.divider()
        
        if st.button("🚀 Start City/District Scraping", type="primary", disabled=st.session_state.is_scraping, use_container_width=True, key="start_city"):
            clear_logs()
            st.session_state.is_scraping = True
            st.session_state.scraping_mode = "city"
            
            # Write runner script
            runner_code = f"""
import sys
import os
sys.path.insert(0, os.getcwd())
from app.scraper.desktop_scraper import scrape_city
scrape_city('{selected_city}', max_limit={max_limit})
"""
            with open("temp_runner.py", "w") as f:
                f.write(runner_code)
            
            # Start process
            st.session_state.scraper_process = subprocess.Popen(
                [
                    r"C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe",
                    "-u",
                    "temp_runner.py"
                ],
                stdout=open(LOG_FILE, "w"),
                stderr=subprocess.STDOUT,
                cwd=r"c:\Users\PC\Documents\trae_projects\Scapre for thozil"
            )
            st.rerun()
    
    # ------------------------------
    # Tab 2: Manual URL Scraping
    # ------------------------------
    with tab_url:
        st.subheader("Scrape a Single JustDial URL")
        
        manual_url = st.text_input(
            "Enter JustDial restaurant URL",
            placeholder="https://www.justdial.com/Kochi/Restaurant-Name-Biz-Details..."
        )
        
        if st.button("🚀 Scrape This URL", type="primary", disabled=st.session_state.is_scraping, use_container_width=True, key="start_url"):
            if not manual_url or "justdial.com" not in manual_url:
                st.error("Please enter a valid JustDial URL!")
            else:
                clear_logs()
                st.session_state.is_scraping = True
                st.session_state.scraping_mode = "url"
                
                # Write runner script for single URL
                runner_code = f"""
import sys
import os
sys.path.insert(0, os.getcwd())
from app.scraper.desktop_scraper import scrape_single_url
scrape_single_url('{manual_url}')
"""
                with open("temp_runner.py", "w") as f:
                    f.write(runner_code)
                
                # Start process
                st.session_state.scraper_process = subprocess.Popen(
                    [
                        r"C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe",
                        "-u",
                        "temp_runner.py"
                    ],
                    stdout=open(LOG_FILE, "w"),
                    stderr=subprocess.STDOUT,
                    cwd=r"c:\Users\PC\Documents\trae_projects\Scapre for thozil"
                )
                st.rerun()
    
    # ------------------------------
    # Controls and Logs (shared)
    # ------------------------------
    st.divider()
    
    col_clear, col_status = st.columns([1, 1])
    
    with col_clear:
        if st.button("🗑️ Clear Logs", use_container_width=True):
            clear_logs()
    
    with col_status:
        if st.session_state.is_scraping and st.session_state.scraper_process:
            if st.session_state.scraper_process.poll() is None:
                status_text = "🔴 Scraping in progress..."
            else:
                st.session_state.is_scraping = False
                status_text = "🟢 Ready"
        else:
            status_text = "🟢 Ready"
        st.metric("Status", status_text)
    
    st.divider()
    
    # Live logs
    st.subheader("📜 Live Scraper Logs")
    log_container = st.container(border=True, height=400)
    
    logs = read_logs()
    with log_container:
        if logs:
            st.markdown(f'<div class="log-container">{logs.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
        else:
            st.info("Logs will appear here when scraping starts...")
    
    # Auto-refresh while scraping
    if st.session_state.is_scraping:
        if st.session_state.scraper_process and st.session_state.scraper_process.poll() is not None:
            st.session_state.is_scraping = False
        time.sleep(1)
        st.rerun()

# ==========================================
# PAGE 4: DATABASE MANAGEMENT
# ==========================================
elif page == "Database Management":
    st.title("Database Management")
    stats = get_stats()

    c1, c2, c3 = st.columns(3)
    c1.metric("Restaurants", stats.get('total_restaurants', 0))
    c2.metric("Images", stats.get('total_images', 0))
    c3.metric("Menu Items", stats.get('total_menu_items', 0))

    st.divider()
    st.subheader("Maintenance Tools")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Delete Duplicates")
        if st.button("Execute Delete Duplicates", type="primary"):
            try:
                res = requests.post(f"{API_URL}/delete-duplicates", timeout=10)
                if res.status_code == 200:
                    st.success(f"Success! Deleted {res.json().get('deleted', 0)} duplicates!")
            except Exception as e:
                st.error(f"Error: {e}")

    with col2:
        st.markdown("### Danger Zone")
        if st.button("Clear All Data"):
            try:
                res = requests.post(f"{API_URL}/clear-all", timeout=10)
                if res.status_code == 200:
                    st.success("Success! All data cleared!")
            except Exception as e:
                st.error(f"Error: {e}")
