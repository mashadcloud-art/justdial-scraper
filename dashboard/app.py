
import streamlit as st
import requests
import threading
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = "http://localhost:8000/api/v1"

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

st.set_page_config(page_title="JustDial Master Control", page_icon="🍽️", layout="wide")
st.markdown("""
    &lt;style&gt;
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; }
    .stButton&gt;button { width: 100%; border-radius: 10px; height: 3em; }
    &lt;/style&gt;
""", unsafe_allow_html=True)

st.sidebar.title("🍽️ JustDial Master")
page = st.sidebar.radio("Go to", ["📊 Dashboard", "📂 Category Management", "🤖 Scraper Control", "🛠️ Database Management"])

def get_stats():
    try:
        res = requests.get(f"{API_URL}/stats", timeout=2)
        if res.status_code == 200: 
            return res.json()
    except: 
        pass
    return {"total_restaurants": 0, "total_images": 0, "total_menu_items": 0}

# ==========================================
# PAGE 1: DASHBOARD
# ==========================================
if page == "📊 Dashboard":
    st.title("📊 Restaurant Dashboard")
    stats = get_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("🏪 Total Restaurants", stats.get('total_restaurants', 0))
    c2.metric("🖼️ Total Images", stats.get('total_images', 0))
    c3.metric("🍽️ Total Menu Items", stats.get('total_menu_items', 0))
    st.divider()
    if st.button("🔄 Refresh Data"): 
        st.rerun()
    try:
        response = requests.get(f"{API_URL}/restaurants", timeout=5)
        if response.status_code == 200:
            restaurants = response.json()
            for r in restaurants:
                with st.container(border=True):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        if r.get('image_path'): 
                            st.image(f"http://localhost:8000/{r['image_path']}", width=300)
                    with col2:
                        st.subheader(r['name'])
                        if r.get('phone'): 
                            st.markdown(f"📞 **Phone:** {r['phone']}")
                        if r.get('whatsapp'): 
                            st.markdown(f"💬 **WhatsApp:** {r['whatsapp']}")
                        if r.get('address'): 
                            st.markdown(f"📍 **Address:** {r['address']}")
                        if r.get('menu_items'):
                            with st.expander(f"🍽️ View Menu ({len(r['menu_items'])} items)"):
                                for item in r['menu_items'][:15]:
                                    veg_icon = "🟢" if item['is_veg'] else "🔴"
                                    st.markdown(f"{veg_icon} **{item['name']}** - ₹{item['price']}")
    except Exception as e: 
        st.error(f"Could not connect to API. Is it running? Error: {e}")

# ==========================================
# PAGE 2: CATEGORY MANAGEMENT
# ==========================================
elif page == "📂 Category Management":
    st.title("📂 Category Management")
    st.markdown("Fetch, select, and manage JustDial categories for scraping")
    
    st.subheader("1️⃣ Fetch Categories from JustDial")
    if st.button("🔄 Fetch All Categories", type="primary"):
        with st.spinner("Fetching categories from JustDial..."):
            try:
                response = requests.get(f"{API_URL}/categories/fetch-from-justdial?city=Mumbai", timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"✅ {data['message']}")
                    st.info(f"📊 Total categories in database: {data['total_categories']}")
                else:
                    st.error(f"Failed to fetch categories: {response.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")
    
    st.divider()
    
    st.subheader("2️⃣ Browse Categories")
    
    col1, col2 = st.columns(2)
    with col1:
        search_term = st.text_input("🔍 Search Categories", placeholder="e.g., Chinese, Hotel, Doctor")
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
            st.write(f"📋 Found **{categories_data['total']}** categories")
            
            if categories_data['categories']:
                st.dataframe(
                    categories_data['categories'],
                    use_container_width=True,
                    height=400
                )
    except Exception as e:
        st.error(f"Failed to load categories: {e}")
    
    st.divider()
    
    st.subheader("3️⃣ Select Categories for Scraping")
    
    col1, col2 = st.columns(2)
    with col1:
        category_id = st.number_input("Category ID", min_value=1, step=1)
    with col2:
        city = st.text_input("City", value="Mumbai", placeholder="e.g., Kochi, Delhi")
    
    if st.button("✅ Select Category"):
        try:
            response = requests.post(
                f"{API_URL}/categories/select",
                params={"category_id": category_id, "city": city},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    st.success(f"✅ {data['message']}")
                else:
                    st.warning(data['message'])
            else:
                st.error(f"Failed: {response.status_code}")
        except Exception as e:
            st.error(f"Error: {e}")
    
    st.divider()
    
    st.subheader("4️⃣ Currently Selected Categories")
    
    try:
        response = requests.get(f"{API_URL}/categories/selected", timeout=10)
        if response.status_code == 200:
            selected_data = response.json()
            if selected_data['selections']:
                st.dataframe(
                    selected_data['selections'],
                    use_container_width=True,
                    height=300
                )
            else:
                st.info("No categories selected yet. Use the form above to select categories.")
    except Exception as e:
        st.error(f"Failed to load selected categories: {e}")

# ==========================================
# PAGE 3: SCRAPER CONTROL
# ==========================================
elif page == "🤖 Scraper Control":
    st.title("🤖 Enterprise Scraper Control")
    st.markdown("Select locations, set limits, and launch the scraper directly from here!")
    
    st.divider()
    
    st.subheader("🌍 1. Select Locations")
    col1, col2 = st.columns(2)
    
    with col1:
        selected_states = st.multiselect("Select State(s)", list(STATE_CITIES.keys()))
        
    available_cities = []
    for state in selected_states:
        available_cities.extend(STATE_CITIES[state])
        
    with col2:
        selected_cities = st.multiselect("Select City/Cities", sorted(list(set(available_cities))))
        
    st.divider()
    st.subheader("⚙️ 2. Scrape Settings")
    col3, col4 = st.columns(2)
    
    with col3:
        scrape_limit = st.selectbox("Number of Restaurants to Scrape per City", [50, 100, 150, 200, 500, "All"])
        
    with col4:
        st.markdown("**OR Scrape a Specific Link:**")
        specific_url = st.text_input("Paste JustDial URL", placeholder="https://www.justdial.com/...")
        
    st.divider()
    
    st.subheader("🚀 3. Execute")
    col5, col6 = st.columns(2)
    
    with col5:
        if st.button("🚀 Scrape Selected Cities", type="primary"):
            if not selected_cities:
                st.error("Please select at least one city!")
            else:
                st.session_state['scrape_status'] = f"Scraping {len(selected_cities)} cities (Limit: {scrape_limit} per city)..."
                
                def run_bulk_scraper():
                    try:
                        from app.scraper.desktop_scraper import scrape_city
                        for city in selected_cities:
                            print(f"\n🚀 [Streamlit] Starting scrape for {city} (Limit: {scrape_limit})...")
                            scrape_city(city, max_limit=scrape_limit)
                            time.sleep(5)
                        print("\n✅ [Streamlit] All cities scraped successfully!")
                    except Exception as e:
                        print(f"\n❌ [Streamlit] Scraping failed: {e}")

                threading.Thread(target=run_bulk_scraper, daemon=True).start()
                st.success(f"🚀 **Scraper launched in background!** Scraping {len(selected_cities)} cities. Check terminal for progress.")
                st.balloons()
                
    with col6:
        if st.button("🎯 Scrape Specific Link", type="primary"):
            if not specific_url or "justdial.com" not in specific_url:
                st.error("Please enter a valid JustDial URL!")
            else:
                st.session_state['scrape_status'] = f"Scraping specific URL..."
                
                def run_single_scraper():
                    try:
                        from app.scraper.desktop_scraper import scrape_single_url
                        print(f"\n🎯 [Streamlit] Starting single URL scrape...")
                        scrape_single_url(specific_url)
                        print("\n✅ [Streamlit] Single URL scraped successfully!")
                    except Exception as e:
                        print(f"\n❌ [Streamlit] Scraping failed: {e}")

                threading.Thread(target=run_single_scraper, daemon=True).start()
                st.success("🎯 **Scraper launched in background!** Scraping specific URL. Check terminal for progress.")
                st.balloons()

    if 'scrape_status' in st.session_state:
        st.info(f"🎯 **Status:** {st.session_state['scrape_status']}")

# ==========================================
# PAGE 4: DATABASE MANAGEMENT
# ==========================================
elif page == "🛠️ Database Management":
    st.title("🛠️ Database Management")
    stats = get_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Restaurants", stats.get('total_restaurants', 0))
    c2.metric("Images", stats.get('total_images', 0))
    c3.metric("Menu Items", stats.get('total_menu_items', 0))
    st.divider()
    st.subheader("🧹 Maintenance Tools")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🗑️ Delete Duplicates")
        if st.button("Execute Delete Duplicates", type="primary"):
            try:
                res = requests.post(f"{API_URL}/delete-duplicates", timeout=10)
                if res.status_code == 200: 
                    st.success(f"✅ Deleted {res.json().get('deleted', 0)} duplicates!")
            except Exception as e: 
                st.error(f"Error: {e}")
    with col2:
        st.markdown("### 💣 Danger Zone")
        if st.button("Clear All Data"):
            try:
                res = requests.post(f"{API_URL}/clear-all", timeout=10)
                if res.status_code == 200: 
                    st.success("✅ All data cleared!")
            except Exception as e: 
                st.error(f"Error: {e}")
