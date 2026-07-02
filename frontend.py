import streamlit as st
import requests
import time
import sys
import os
import subprocess
from datetime import datetime

# Add parent directory to path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app import models

API_URL = "http://127.0.0.1:8000/api/v1"
LOG_FILE = "scraper_logs.txt"
PYTHON_EXE = sys.executable


# Initialize session state
if 'is_scraping' not in st.session_state:
    st.session_state.is_scraping = False
if 'scraper_process' not in st.session_state:
    st.session_state.scraper_process = None
if 'is_scrolling' not in st.session_state:
    st.session_state.is_scrolling = False
if 'scroll_process' not in st.session_state:
    st.session_state.scroll_process = None

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
    "Database Management",
    "Module Shop"
])

st.sidebar.divider()
st.sidebar.subheader("Backend Services")

backend_online = False
try:
    res = requests.get("http://127.0.0.1:8000/api/v1/stats", timeout=5.0)
    if res.status_code == 200:
        backend_online = True
except Exception:
    pass

if backend_online:
    st.sidebar.success("🟢 Local Backend: Active")
    try:
        db_res = requests.get(f"{API_URL}/db-status", timeout=2.0)
        if db_res.status_code == 200:
            db_status = db_res.json()
            if db_status.get("connected"):
                st.sidebar.success(f"🟢 Database: Connected\n({db_status.get('type')})")
            else:
                st.sidebar.error("🔴 Database: Disconnected")
        else:
            st.sidebar.error("🔴 Database: Offline")
    except Exception:
        st.sidebar.error("🔴 Database: Connection Failed")
else:
    st.sidebar.error("🔴 Local Backend: Offline")
    if st.sidebar.button("🚀 Start Local Backend"):
        # Start FastAPI backend process in background
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=open("backend_start.log", "w"),
            stderr=subprocess.STDOUT,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        st.sidebar.info("Starting backend... Please wait 3 seconds.")
        time.sleep(3)
        st.rerun()

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

def get_all_restaurants(limit=100):
    """Fetch recent restaurants (limited to avoid UI freeze)"""
    all_data = []
    try:
        res = requests.get(f"{API_URL}/restaurants", params={"page": 1, "limit": limit}, timeout=10)
        if res.status_code == 200:
            resp = res.json()
            if isinstance(resp, list):
                all_data = resp
            else:
                all_data = resp.get("data", [])
    except:
        pass
    return all_data

def clear_logs():
    try:
        # Truncate instead of delete — safe even when subprocess holds the file open
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("")
    except Exception:
        pass

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
        restaurants = get_all_restaurants()
        if restaurants:
            for r in restaurants:
                with st.container(border=True):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        if r.get('image_path'):
                            img_path = r['image_path']
                            if img_path.startswith("http://") or img_path.startswith("https://"):
                                st.image(img_path, width=300)
                            else:
                                st.image(f"http://127.0.0.1:8000/{img_path}", width=300)
                    with col2:
                        st.subheader(r.get('name', 'Unknown'))
                        if r.get('phone'):
                            st.markdown(f"**Phone:** {r['phone']}")
                        if r.get('whatsapp'):
                            st.markdown(f"**WhatsApp:** {r['whatsapp']}")
                        if r.get('address'):
                            st.markdown(f"**Address:** {r['address']}")
                        if r.get('latitude') and r.get('longitude'):
                            st.markdown(f"**Location:** Lat {r['latitude']}, Lon {r['longitude']}")

                        if r.get('menu_items'):
                            with st.expander(f"View Menu ({len(r['menu_items'])} items)"):
                                for item in r['menu_items'][:15]:
                                    veg_text = "Veg" if item.get('is_veg') else "Non-Veg"
                                    st.markdown(f"**{item.get('name', 'Unknown')}** - ₹{item.get('price', 'N/A')} ({veg_text})")
                                    
                        if r.get('images') and len(r['images']) > 1:
                            with st.expander(f"🖼️ View Gallery ({len(r['images'])} photos)"):
                                cols = st.columns(4)
                                for idx, img_obj in enumerate(r['images']):
                                    img_url = img_obj.get('path')
                                    if img_url:
                                        if not (img_url.startswith("http://") or img_url.startswith("https://")):
                                            img_url = f"http://127.0.0.1:8000/{img_url}"
                                        cols[idx % 4].image(img_url, use_container_width=True)
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
    tab_city, tab_url, tab_gmaps, tab_scroll, tab_custom = st.tabs(["🏙️ City/District-Wise Scraping", "🔗 Manual URL Scraping", "🗺️ Google Maps Scraper", "📱 Manual Auto-Scroll (ADB)", "💻 Custom Command Run"])
    
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
                    PYTHON_EXE,
                    "-u",
                    "temp_runner.py"
                ],
                stdout=open(LOG_FILE, "w"),
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(os.path.abspath(__file__))
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
                        PYTHON_EXE,
                        "-u",
                        "temp_runner.py"
                    ],
                    stdout=open(LOG_FILE, "w"),
                    stderr=subprocess.STDOUT,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                st.rerun()
                
    # ------------------------------
    # Tab 3: Google Maps Scraper (Generic)
    # ------------------------------
    with tab_gmaps:
        st.subheader("Google Maps Kerala Scraper")
        st.markdown("Scrape any business category (e.g. Restaurants, Cafes, Hospitals) across pincodes in a Kerala district.")
        
        col_q, col_d = st.columns(2)
        with col_q:
            gmaps_query = st.text_input("Google Maps Query", value="restaurants", placeholder="e.g. restaurants, cafes, hotels, dentists")
        with col_d:
            gmaps_district = st.selectbox(
                "Select District",
                ["Kasaragod", "Kannur", "Wayanad", "Kozhikode", "Malappuram", "Palakkad", "Thrissur", "Ernakulam", "Idukki", "Kottayam", "Alappuzha", "Pathanamthitta", "Kollam", "Thiruvananthapuram"],
                index=0
            )
            
        col_cat, col_ncat = st.columns(2)
        with col_cat:
            gmaps_category = st.text_input("Category (DB classification)", value="Restaurants", placeholder="e.g. Restaurants, Cafes, Hospitals")
        with col_ncat:
            gmaps_normalized = st.selectbox(
                "Normalized Category (DB parent)",
                ["Food & Restaurants", "Health & Medical", "Education", "Accommodation", "Shopping & Retail", "Automotive", "Beauty & Spa", "Services", "Others"],
                index=0
            )
            
        col_lim, col_ph = st.columns(2)
        with col_lim:
            gmaps_limit_pins = st.number_input("Limit Pincodes (0 for all)", min_value=0, value=0, step=1)
        with col_ph:
            gmaps_max_photos = st.slider("Max Photos per Place", min_value=1, max_value=500, value=50)
            
        gmaps_live = st.toggle("Live Mode (Write to Supabase database)", value=False)
        gmaps_auto_bg = st.toggle("☑️ Automatically run Background Deep Scraper too (Hybrid Mode)", value=True)
        
        st.divider()
        
        # --- CLOUD SHELL COMMANDS GENERATOR ---
        st.markdown("### ☁️ Cloud Terminal Command Generator")
        st.info("Copy these commands and paste them directly into your remote cloud VM shell (e.g. SSH terminal) to run the scrape off-device:")
        
        # Build the exact commands dynamically based on input fields above
        fast_cmd_str = f"python3 -u scrape_gmaps_general.py --district \"{gmaps_district}\" --query \"{gmaps_query}\" --category \"{gmaps_category}\" --normalized-category \"{gmaps_normalized}\" --live"
        deep_cmd_str = f"python3 -u app/scraper/scrape_background_images.py --district \"{gmaps_district}\" --category \"{gmaps_category}\""
        
        st.markdown("**1. Run Fast Scraper (in background):**")
        st.code(f"nohup {fast_cmd_str} > fast_scraper.log 2>&1 &", language="bash")
        
        st.markdown("**2. Run Deep Image & Menu Scraper (in background):**")
        st.code(f"nohup {deep_cmd_str} > deep_daemon.log 2>&1 &", language="bash")
        
        st.markdown("---")

        if st.button("🚀 Start Google Maps Scraper", type="primary", disabled=st.session_state.is_scraping, use_container_width=True, key="start_gmaps"):
            clear_logs()
            st.session_state.is_scraping = True
            st.session_state.scraping_mode = "gmaps"
            
            # Start background daemon if requested
            if gmaps_auto_bg:
                bg_args = [PYTHON_EXE, "-u", "app/scraper/scrape_background_images.py"]
                if gmaps_category:
                    bg_args.extend(["--category", gmaps_category])
                    
                subprocess.Popen(
                    bg_args,
                    stdout=open("bg_scraper_logs.txt", "w"),
                    stderr=subprocess.STDOUT,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                st.toast("Background Daemon started!")
            
            # Build CLI arguments
            args_list = [
                PYTHON_EXE,
                "-u",
                "scrape_gmaps_general.py",
                "--district", gmaps_district,
                "--query", gmaps_query,
                "--category", gmaps_category,
                "--normalized-category", gmaps_normalized,
                "--max-photos", str(gmaps_max_photos)
            ]
            if gmaps_live:
                args_list.append("--live")
            if gmaps_limit_pins > 0:
                args_list.extend(["--limit-pins", str(gmaps_limit_pins)])
                
            # Start process
            st.session_state.scraper_process = subprocess.Popen(
                args_list,
                stdout=open(LOG_FILE, "w"),
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            st.rerun()
            
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🤖 Start Background Image Scraper (Hybrid Mode)", type="secondary", disabled=st.session_state.is_scraping, use_container_width=True, key="start_bg_scraper"):
            clear_logs()
            st.session_state.is_scraping = True
            st.session_state.scraping_mode = "bg_images"
            
            # Start background scraper process
            st.session_state.scraper_process = subprocess.Popen(
                [PYTHON_EXE, "-u", "app/scraper/scrape_background_images.py"],
                stdout=open(LOG_FILE, "w"),
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            st.rerun()

    # ------------------------------
    # Tab 4: Manual Auto-Scroll (ADB)
    # ------------------------------
    with tab_scroll:
        st.subheader("Manual Auto-Scroll via ADB")
        st.info("Use this if you navigated to a page on your Android device manually and just want the script to swipe up continuously to load more items.")
        
        scroll_interval = st.number_input("Seconds between swipes", min_value=0.5, max_value=10.0, value=3.0, step=0.5)
        
        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("▶️ Start Auto-Scrolling", type="primary", disabled=st.session_state.is_scrolling, use_container_width=True):
                st.session_state.is_scrolling = True
                st.session_state.scroll_process = subprocess.Popen(
                    [
                        PYTHON_EXE,
                        "-u", "-m", "app.scraper.adb_controller",
                        "--interval", str(scroll_interval)
                    ],
                    stdout=open(LOG_FILE, "a"),
                    stderr=subprocess.STDOUT,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                st.rerun()
                
        with col_stop:
            if st.button("🛑 Stop Auto-Scrolling", type="secondary", disabled=not st.session_state.is_scrolling, use_container_width=True):
                if st.session_state.scroll_process:
                    st.session_state.scroll_process.terminate()
                    st.session_state.scroll_process = None
                st.session_state.is_scrolling = False
                with open(LOG_FILE, "a") as f:
                    f.write("\n🛑 Auto-scroll stopped manually from UI.\n")
                st.rerun()
    
    # ------------------------------
    # Tab 5: Custom CLI Command Run
    # ------------------------------
    with tab_custom:
        st.subheader("Run Custom Command Line Scraper")
        st.info("Directly run any scraper or script with your own arguments from your phone, tablet, or another device.")
        
        # User input for script
        custom_script = st.selectbox(
            "Select Script to Run",
            [
                "scrape_gmaps_general.py (Google Maps Scraper)",
                "jd_api_scraper.py (JustDial API Scraper)",
                "deduplicate_db.py (Database Deduplication)",
                "clear_jithu.py (Database cleaner utility)",
                "Custom Python script/command..."
            ]
        )
        
        # If "Custom python script/command...", allow typing script name
        if custom_script.startswith("Custom"):
            run_cmd = st.text_input("Full Python command", placeholder="e.g. scrape_gmaps_general.py --district Kasaragod --query \"Heal Pharmacy\" --category \"Pharmacies\" --normalized-category \"Health & Medical\" --max-photos 1000 --live")
        else:
            script_file = custom_script.split(" ")[0]
            args_input = st.text_area("Arguments / Flags", value='--district Kasaragod --query "Heal Pharmacy" --category "Pharmacies" --normalized-category "Health & Medical" --max-photos 1000 --live', placeholder="e.g. --district Idukki --query \"pharmacy\" --category \"Pharmacies\" --max-photos 1000 --live")
            run_cmd = f"{script_file} {args_input}"
            
        st.code(f"{PYTHON_EXE} -u {run_cmd}", language="bash")
        
        if st.button("🚀 Execute Custom Command", type="primary", disabled=st.session_state.is_scraping, use_container_width=True, key="run_custom_cmd"):
            if not run_cmd.strip():
                st.error("Command cannot be empty!")
            else:
                clear_logs()
                st.session_state.is_scraping = True
                st.session_state.scraping_mode = "custom"
                
                # Split args correctly handling quotes
                import shlex
                try:
                    args_split = shlex.split(run_cmd)
                except Exception as e:
                    st.error(f"Failed to parse command arguments: {e}")
                    st.session_state.is_scraping = False
                    st.stop()
                    
                # Full arguments list
                full_args = [PYTHON_EXE, "-u"] + args_split
                
                # Start process
                st.session_state.scraper_process = subprocess.Popen(
                    full_args,
                    stdout=open(LOG_FILE, "w"),
                    stderr=subprocess.STDOUT,
                    cwd=os.path.dirname(os.path.abspath(__file__))
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
        elif st.session_state.is_scrolling and st.session_state.scroll_process:
            if st.session_state.scroll_process.poll() is None:
                status_text = "🔄 Auto-Scrolling in progress..."
            else:
                st.session_state.is_scrolling = False
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
    if st.session_state.is_scraping or st.session_state.is_scrolling:
        if st.session_state.is_scraping and st.session_state.scraper_process and st.session_state.scraper_process.poll() is not None:
            st.session_state.is_scraping = False
        if st.session_state.is_scrolling and st.session_state.scroll_process and st.session_state.scroll_process.poll() is not None:
            st.session_state.is_scrolling = False
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
    st.subheader("Database Configuration")
    
    import yaml
    from app_config import CONFIG_FILE
    
    current_config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                current_config = yaml.safe_load(f) or {}
        except Exception:
            pass

    db_url = current_config.get("database", {}).get("url") or ""
    sb_url = current_config.get("supabase", {}).get("url") or ""
    sb_key = current_config.get("supabase", {}).get("anon_key") or ""
    
    with st.form("db_config_form"):
        new_db_url = st.text_input("Database Connection URL (Postgres or SQLite)", value=db_url, help="Supabase/Postgres Connection String")
        new_sb_url = st.text_input("Supabase Project URL", value=sb_url, help="https://xxxx.supabase.co")
        new_sb_key = st.text_input("Supabase Anon Key", value=sb_key, type="password")
        
        submitted = st.form_submit_button("Save & Update Database Config")
        if submitted:
            payload = {
                "db_url": new_db_url,
                "supabase_url": new_sb_url,
                "supabase_anon_key": new_sb_key
            }
            try:
                res = requests.post(f"{API_URL}/db-config", json=payload, timeout=10)
                if res.status_code == 200:
                    st.success("Config updated successfully! Restarting the backend server to apply changes...")
                    try:
                        requests.post(f"{API_URL}/system/restart", timeout=2)
                    except Exception:
                        pass
                    time.sleep(3)
                    st.rerun()
                else:
                    st.error(f"Failed to update config: {res.text}")
            except Exception as e:
                st.error(f"Error: {e}")

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

# ==========================================
# PAGE 5: MODULE SHOP
# ==========================================
elif page == "Module Shop":
    st.title("🧩 Module Shop")
    st.markdown("Manage and run dynamic plugins without restarting the app.")
    
    try:
        from core.plugin_manager import PluginManager
        pm = PluginManager(os.path.dirname(os.path.abspath(__file__)))
        plugins = pm.discover_plugins()
        
        if not plugins:
            st.info("No plugins installed in the 'modules' folder.")
        else:
            for p in plugins:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.subheader(p['name'])
                        st.caption(f"v{p['version']} | Author: {p['author']}")
                        st.write(p['description'])
                    with col2:
                        enabled = st.toggle("Enable Plugin", value=p['enabled'], key=f"tog_{p['id']}")
                        if enabled != p['enabled']:
                            pm.toggle_plugin(p['id'], enabled)
                            st.rerun()
                    with col3:
                        if p['enabled']:
                            if st.button("▶ Run Plugin", key=f"run_{p['id']}", use_container_width=True):
                                with st.spinner(f"Running {p['name']}..."):
                                    res = pm.run_plugin(p['id'], app_data={"context": "streamlit"})
                                    if res['status'] == 'success':
                                        st.success("Executed successfully!")
                                        st.json(res['data'])
                                    else:
                                        st.error(res['message'])
                                        if 'traceback' in res:
                                            with st.expander("Show Traceback"):
                                                st.code(res['traceback'])
                        else:
                            st.button("▶ Run Plugin", disabled=True, key=f"run_disabled_{p['id']}", use_container_width=True)
                            
    except Exception as e:
        st.error(f"Failed to load Module Shop: {e}")
