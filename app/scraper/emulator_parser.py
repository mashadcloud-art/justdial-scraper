import json
import time
import os
import re
import requests
from typing import List, Dict, Any, Optional
from app.scraper.logger import log
from app.scraper.api_scraper import clean_phone, parse_api_row, upload_to_api

# ─── Auto-assign state from district ───────────────────────────────────────────
DISTRICT_TO_STATE: Dict[str, str] = {
    # Andhra Pradesh
    "Visakhapatnam": "Andhra Pradesh", "Vijayawada": "Andhra Pradesh", "Guntur": "Andhra Pradesh",
    "Nellore": "Andhra Pradesh", "Kurnool": "Andhra Pradesh", "Tirupati": "Andhra Pradesh",
    "Rajahmundry": "Andhra Pradesh", "Kakinada": "Andhra Pradesh", "Anantapur": "Andhra Pradesh",
    "Eluru": "Andhra Pradesh", "Ongole": "Andhra Pradesh", "Srikakulam": "Andhra Pradesh",
    "Vizianagaram": "Andhra Pradesh", "Chittoor": "Andhra Pradesh", "Kadapa": "Andhra Pradesh",
    # Assam
    "Guwahati": "Assam", "Silchar": "Assam", "Dibrugarh": "Assam", "Jorhat": "Assam",
    "Nagaon": "Assam", "Tezpur": "Assam", "Tinsukia": "Assam",
    # Bihar
    "Patna": "Bihar", "Gaya": "Bihar", "Bhagalpur": "Bihar", "Muzaffarpur": "Bihar",
    "Darbhanga": "Bihar", "Purnia": "Bihar",
    # Chhattisgarh
    "Raipur": "Chhattisgarh", "Bhilai": "Chhattisgarh", "Bilaspur": "Chhattisgarh",
    "Korba": "Chhattisgarh", "Durg": "Chhattisgarh",
    # Goa
    "Panaji": "Goa", "Margao": "Goa", "Vasco da Gama": "Goa", "Mapusa": "Goa", "Ponda": "Goa",
    # Gujarat
    "Ahmedabad": "Gujarat", "Surat": "Gujarat", "Vadodara": "Gujarat", "Rajkot": "Gujarat",
    "Bhavnagar": "Gujarat", "Jamnagar": "Gujarat", "Gandhinagar": "Gujarat", "Junagadh": "Gujarat",
    "Anand": "Gujarat", "Navsari": "Gujarat", "Morbi": "Gujarat",
    # Haryana
    "Faridabad": "Haryana", "Gurgaon": "Haryana", "Panipat": "Haryana", "Ambala": "Haryana",
    "Hisar": "Haryana", "Karnal": "Haryana", "Rohtak": "Haryana", "Sonipat": "Haryana",
    # Himachal Pradesh
    "Shimla": "Himachal Pradesh", "Mandi": "Himachal Pradesh", "Dharamshala": "Himachal Pradesh",
    "Solan": "Himachal Pradesh", "Kullu": "Himachal Pradesh", "Manali": "Himachal Pradesh",
    # Jharkhand
    "Ranchi": "Jharkhand", "Jamshedpur": "Jharkhand", "Dhanbad": "Jharkhand",
    "Bokaro": "Jharkhand", "Hazaribagh": "Jharkhand",
    # Karnataka
    "Bengaluru": "Karnataka", "Bangalore": "Karnataka", "Mysuru": "Karnataka", "Mysore": "Karnataka",
    "Mangaluru": "Karnataka", "Mangalore": "Karnataka", "Hubli": "Karnataka",
    "Belagavi": "Karnataka", "Belgaum": "Karnataka", "Kalaburagi": "Karnataka",
    "Davangere": "Karnataka", "Shivamogga": "Karnataka", "Tumkur": "Karnataka",
    "Udupi": "Karnataka", "Dharwad": "Karnataka", "Ballari": "Karnataka",
    "Hassan": "Karnataka", "Bidar": "Karnataka", "Raichur": "Karnataka",
    "Vijayapura": "Karnataka", "Bagalkot": "Karnataka", "Mandya": "Karnataka",
    "Chikkamagaluru": "Karnataka", "Kodagu": "Karnataka",
    # Kerala
    "Thiruvananthapuram": "Kerala", "Trivandrum": "Kerala",
    "Kollam": "Kerala", "Pathanamthitta": "Kerala", "Alappuzha": "Kerala", "Alleppey": "Kerala",
    "Kottayam": "Kerala", "Idukki": "Kerala", "Ernakulam": "Kerala", "Kochi": "Kerala",
    "Thrissur": "Kerala", "Trichur": "Kerala", "Palakkad": "Kerala", "Palghat": "Kerala",
    "Malappuram": "Kerala", "Kozhikode": "Kerala", "Calicut": "Kerala",
    "Wayanad": "Kerala", "Kannur": "Kerala", "Cannanore": "Kerala",
    "Kasaragod": "Kerala", "Kasargod": "Kerala",
    "Thiruvalla": "Kerala", "Thrippunithura": "Kerala", "Kalamassery": "Kerala",
    "Perumbavoor": "Kerala", "Muvattupuzha": "Kerala", "Angamaly": "Kerala",
    "Chalakudy": "Kerala", "Irinjalakuda": "Kerala", "Guruvayur": "Kerala",
    "Kunnamkulam": "Kerala", "Ponnani": "Kerala", "Tirur": "Kerala",
    "Manjeri": "Kerala", "Kalpetta": "Kerala", "Thalassery": "Kerala",
    "Vatakara": "Kerala", "Payyannur": "Kerala",
    # Madhya Pradesh
    "Bhopal": "Madhya Pradesh", "Indore": "Madhya Pradesh", "Gwalior": "Madhya Pradesh",
    "Jabalpur": "Madhya Pradesh", "Ujjain": "Madhya Pradesh", "Sagar": "Madhya Pradesh",
    "Ratlam": "Madhya Pradesh", "Rewa": "Madhya Pradesh",
    # Maharashtra
    "Mumbai": "Maharashtra", "Pune": "Maharashtra", "Nagpur": "Maharashtra",
    "Thane": "Maharashtra", "Nashik": "Maharashtra", "Aurangabad": "Maharashtra",
    "Solapur": "Maharashtra", "Navi Mumbai": "Maharashtra", "Pimpri-Chinchwad": "Maharashtra",
    "Amravati": "Maharashtra", "Kolhapur": "Maharashtra", "Sangli": "Maharashtra",
    "Nanded": "Maharashtra", "Akola": "Maharashtra", "Latur": "Maharashtra",
    "Dhule": "Maharashtra", "Ahmednagar": "Maharashtra", "Chandrapur": "Maharashtra",
    # Delhi
    "New Delhi": "Delhi", "Delhi": "Delhi", "North Delhi": "Delhi", "South Delhi": "Delhi",
    "East Delhi": "Delhi", "West Delhi": "Delhi", "Dwarka": "Delhi", "Rohini": "Delhi",
    # Rajasthan
    "Jaipur": "Rajasthan", "Jodhpur": "Rajasthan", "Udaipur": "Rajasthan",
    "Kota": "Rajasthan", "Ajmer": "Rajasthan", "Bikaner": "Rajasthan", "Alwar": "Rajasthan",
    # Tamil Nadu
    "Chennai": "Tamil Nadu", "Coimbatore": "Tamil Nadu", "Madurai": "Tamil Nadu",
    "Tiruchirappalli": "Tamil Nadu", "Salem": "Tamil Nadu", "Tirunelveli": "Tamil Nadu",
    "Erode": "Tamil Nadu", "Vellore": "Tamil Nadu", "Tiruppur": "Tamil Nadu",
    "Nagercoil": "Tamil Nadu", "Kanchipuram": "Tamil Nadu", "Thanjavur": "Tamil Nadu",
    "Dindigul": "Tamil Nadu", "Karur": "Tamil Nadu", "Cuddalore": "Tamil Nadu",
    "Viluppuram": "Tamil Nadu", "Nagapattinam": "Tamil Nadu",
    # Telangana
    "Hyderabad": "Telangana", "Warangal": "Telangana", "Nizamabad": "Telangana",
    "Karimnagar": "Telangana", "Khammam": "Telangana",
    # Uttar Pradesh
    "Lucknow": "Uttar Pradesh", "Kanpur": "Uttar Pradesh", "Agra": "Uttar Pradesh",
    "Varanasi": "Uttar Pradesh", "Meerut": "Uttar Pradesh", "Prayagraj": "Uttar Pradesh",
    "Ghaziabad": "Uttar Pradesh", "Noida": "Uttar Pradesh", "Bareilly": "Uttar Pradesh",
    "Aligarh": "Uttar Pradesh", "Gorakhpur": "Uttar Pradesh",
    # West Bengal
    "Kolkata": "West Bengal", "Howrah": "West Bengal", "Durgapur": "West Bengal",
    "Asansol": "West Bengal", "Siliguri": "West Bengal", "Bardhaman": "West Bengal",
    "Malda": "West Bengal", "Kharagpur": "West Bengal",
    # Punjab
    "Ludhiana": "Punjab", "Amritsar": "Punjab", "Jalandhar": "Punjab", "Patiala": "Punjab",
    "Bathinda": "Punjab", "Mohali": "Punjab", "Pathankot": "Punjab",
    # Odisha
    "Bhubaneswar": "Odisha", "Cuttack": "Odisha", "Rourkela": "Odisha",
    "Berhampur": "Odisha", "Sambalpur": "Odisha", "Puri": "Odisha",
    # Uttarakhand
    "Dehradun": "Uttarakhand", "Haridwar": "Uttarakhand", "Roorkee": "Uttarakhand",
    "Haldwani": "Uttarakhand", "Rudrapur": "Uttarakhand", "Rishikesh": "Uttarakhand",
    "Nainital": "Uttarakhand", "Mussoorie": "Uttarakhand",
    # J&K
    "Srinagar": "Jammu & Kashmir", "Jammu": "Jammu & Kashmir", "Anantnag": "Jammu & Kashmir",
    "Baramulla": "Jammu & Kashmir",
}

def get_state_from_district(district: str) -> str:
    """Auto-infer the state from the district name."""
    if not district:
        return ""
    # Try exact match first
    if district in DISTRICT_TO_STATE:
        return DISTRICT_TO_STATE[district]
    # Try case-insensitive match
    dist_lower = district.lower()
    for key, val in DISTRICT_TO_STATE.items():
        if key.lower() == dist_lower:
            return val
    return ""

# ─── Known sub-localities / places within Kerala districts ────────────────────
# Any address containing these will set place= automatically
KERALA_PLACES = {
    # Idukki
    "Kuttikkanam", "Kumily", "Thekkady", "Munnar", "Adimali", "Thodupuzha",
    "Nedumkandam", "Painavu", "Vannapuram", "Elappara", "Peermade", "Rajakad",
    "Karimannoor", "Moovattupuzha", "Kothamangalam",
    # Kasaragod
    "Karandakkad", "Padanakkad", "Poinachi", "Kanhangad", "Nileshwar", "Nileshwaram",
    "Adkathbail", "Panathur", "Kasaragod", "Trikaripur", "Cheruvathur", "Uppala",
    "Kumbla", "Manjeshwar", "Manjeshwaram", "Adoor", "Badiadka", "Mulleria",
    "Bekal", "Achanthuruthi", "Achanthuruth", "Karindalam", "Cheemeni", "Pilicode",
    "Neeleswaram", "Neeleshwaram",
    # Ernakulam
    "Edapally", "Aluva", "Perumbavoor", "Muvattupuzha", "Angamaly",
    "Kalamassery", "Thrippunithura", "Piravom", "Kothamangalam",
    # Thrissur
    "Guruvayur", "Irinjalakuda", "Kodungallur", "Chalakudy", "Kunnamkulam",
    "Chavakkad", "Ollur", "Mala",
    # Kozhikode
    "Vatakara", "Koyilandy", "Ramanattukara", "Feroke", "Beypore",
    # Kannur
    "Thalassery", "Payyannur", "Mattannur", "Iritty", "Koothuparamba",
    # Malappuram
    "Tirur", "Manjeri", "Perinthalmanna", "Ponnani", "Kondotty", "Valanchery",
    # Palakkad
    "Ottapalam", "Shoranur", "Mannarkkad", "Chittur",
    # Wayanad
    "Kalpetta", "Mananthavady", "Sulthan Bathery",
    # Thiruvananthapuram
    "Attingal", "Neyyattinkara", "Varkala",
    # Kollam
    "Punalur", "Paravur", "Karunagappally",
    # Alappuzha
    "Cherthala", "Kayamkulam", "Mavelikkara", "Haripad",
    # Kottayam
    "Pala", "Ettumanoor", "Changanassery", "Vaikom",
}

# Known Kerala Towns/Municipalities
KERALA_TOWNS = {
    "Nileshwar", "Nileshwaram", "Neeleswaram", "Neeleshwaram", "Kanhangad", "Kasaragod", "Kasargod",
    "Trikaripur", "Cheruvathur", "Manjeshwar", "Manjeshwaram", "Uppala", "Kumbla",
    "Thiruvananthapuram", "Trivandrum", "Kollam", "Pathanamthitta", "Alappuzha", "Alleppey",
    "Kottayam", "Idukki", "Ernakulam", "Kochi", "Cochin", "Thrissur", "Trichur", "Palakkad", "Palghat",
    "Malappuram", "Kozhikode", "Calicut", "Wayanad", "Kannur", "Cannanore",
    "Thiruvalla", "Thrippunithura", "Kalamassery", "Perumbavoor", "Muvattupuzha", "Angamaly",
    "Chalakudy", "Irinjalakuda", "Guruvayur", "Kunnamkulam", "Ponnani", "Tirur", "Manjeri",
    "Kalpetta", "Thalassery", "Vatakara", "Payyannur"
}

# Building / complex type detection
BUILDING_KEYWORDS = {
    "trade center": "Trade Centers",
    "trade centre": "Trade Centers",
    "shopping mall": "Shopping Malls",
    "mall": "Shopping Malls",
    "shopping complex": "Shopping Complexes",
    "complex": "Commercial Complexes",
    "tower": "Towers & Buildings",
    "towers": "Towers & Buildings",
    "plaza": "Plazas & Arcades",
    "arcade": "Plazas & Arcades",
    "market": "Markets",
    "business park": "Business Parks",
    "tech park": "Tech Parks",
    "industrial estate": "Industrial Areas",
    "hospital": "Hospitals",
    "clinic": "Clinics",
    "hotel": "Hotels",
    "resort": "Resorts",
    "home stay": "Home Stays",
    "homestay": "Home Stays",
    "guest house": "Guest Houses",
    "lodge": "Lodges",
    "school": "Schools",
    "college": "Colleges",
    "institute": "Educational Institutes",
    "academy": "Educational Institutes",
    "bank": "Banks & Finance",
    "atm": "Banks & Finance",
}

def extract_district_from_address(address: str) -> Optional[str]:
    """
    Scans the address to extract the district name based on DISTRICT_TO_STATE.
    Returns the canonical district name closest to the end of the address, or None.
    """
    if not address:
        return None
    addr_clean = " " + " ".join(address.split()) + " "
    addr_lower = addr_clean.lower()
    
    best_dist = None
    max_index = -1
    
    for dist in DISTRICT_TO_STATE.keys():
        dist_lower = dist.lower()
        pattern = r'(?:\b|(?<=_))' + re.escape(dist_lower) + r'(?:\b|(?=_))'
        for match in re.finditer(pattern, addr_lower):
            idx = match.start()
            if idx > max_index:
                max_index = idx
                best_dist = dist
                
    return best_dist

def extract_place_from_address(address: str, district: str) -> str:
    """
    Extracts the specific locality/place from address.
    e.g. 'Nileshwar Achanthuruthi, Kasaragod' -> 'Achanthuruthi, Nileshwar'
         'Ashwin Nagar Karandakkad, Kasaragod' -> 'Ashwin Nagar, Karandakkad'
    """
    if not address:
        return ""
        
    addr_clean = address.strip()
    parts = [p.strip() for p in addr_clean.split(",") if p.strip()]
    if not parts:
        return ""
        
    filtered_parts = []
    for part in parts:
        part_lower = part.lower()
        if re.match(r'^\d{6}$', part):
            continue
        if district and part_lower == district.lower():
            continue
        if part_lower == "kerala":
            continue
        filtered_parts.append(part)
        
    if not filtered_parts:
        return ""
        
    # Find all matches of KERALA_PLACES in the address
    matched_places = []
    addr_lower = addr_clean.lower()
    for place in KERALA_PLACES:
        place_lower = place.lower()
        pattern = r'\b' + re.escape(place_lower) + r'\b'
        if re.search(pattern, addr_lower):
            for match in re.finditer(pattern, addr_lower):
                matched_places.append((place, match.start()))
                
    matched_places = sorted(list(set(matched_places)), key=lambda x: x[1])
    
    unique_matches = []
    seen = set()
    for p, idx in matched_places:
        if p.lower() not in seen:
            unique_matches.append(p)
            seen.add(p.lower())
            
    # Filter out any matched place that is the same as the district (e.g. Kasaragod)
    if district:
        unique_matches = [p for p in unique_matches if p.lower() != district.lower()]
            
    if unique_matches:
        if len(unique_matches) >= 2:
            towns = [p for p in unique_matches if p in KERALA_TOWNS]
            local_places = [p for p in unique_matches if p not in KERALA_TOWNS]
            
            if towns and local_places:
                return f"{local_places[0]}, {towns[0]}"
            else:
                return ", ".join(unique_matches[:2])
                
        matched_town = unique_matches[0]
        matched_part_idx = -1
        for i, part in enumerate(filtered_parts):
            if matched_town.lower() in part.lower():
                matched_part_idx = i
                break
                
        if matched_part_idx != -1:
            target_part = filtered_parts[matched_part_idx]
            words = target_part.split()
            local_words = []
            for word in words:
                word_clean = re.sub(r'[^\w\s]', '', word).strip()
                word_lower = word_clean.lower()
                if not word_clean:
                    continue
                if word_lower == matched_town.lower():
                    continue
                if district and word_lower == district.lower():
                    continue
                skip_keywords = {"road", "nh", "near", "opposite", "opp", "floor", "building", "shop", "street", "highway", "main"}
                if word_lower in skip_keywords:
                    continue
                if word_lower in [k.lower() for k in BUILDING_KEYWORDS.keys()]:
                    continue
                if word_clean.isdigit():
                    continue
                local_words.append(word_clean)
                
            if local_words:
                local_area = " ".join(local_words)
                return f"{local_area}, {matched_town}"
            else:
                if matched_part_idx > 0:
                    prev_part = filtered_parts[matched_part_idx - 1]
                    prev_words = prev_part.split()
                    clean_prev_words = []
                    for word in prev_words:
                        word_clean = re.sub(r'[^\w\s]', '', word).strip()
                        word_lower = word_clean.lower()
                        if word_clean and word_lower not in [k.lower() for k in BUILDING_KEYWORDS.keys()] and not word_clean.isdigit():
                            clean_prev_words.append(word_clean)
                    if clean_prev_words:
                        local_area = " ".join(clean_prev_words[-2:])
                        return f"{local_area}, {matched_town}"
                return matched_town
                
    locality_segment = parts[-2].strip() if len(parts) >= 2 else parts[0].strip()
    words = locality_segment.split()
    if words:
        skip_keywords = {"road", "nh", "near", "opposite", "opp", "floor", "building", "shop", "street", "highway", "main", "nagar"}
        for word in reversed(words):
            word_clean = re.sub(r'[^\w\s]', '', word).strip()
            word_lower = word_clean.lower()
            if not word_clean:
                continue
            if word_lower in skip_keywords:
                continue
            if word_clean.isdigit():
                continue
            if district and word_lower == district.lower():
                continue
            if len(word_clean) > 2:
                return word_clean
            
    return ""

def detect_category_from_name(name: str, current_category: str) -> str:
    """
    Detects business type from name keywords.
    e.g. 'Maryam Trade Center' -> 'Trade Centers'
    """
    if not name:
        return current_category
    name_lower = name.lower()
    for keyword, cat in BUILDING_KEYWORDS.items():
        if keyword in name_lower:
            return cat
    return current_category

# Caching Reverse Geocoder File Path
GEO_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "geocoding_cache.json")

def load_geo_cache() -> Dict[str, Any]:
    if os.path.exists(GEO_CACHE_FILE):
        try:
            with open(GEO_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_geo_cache(cache: Dict[str, Any]):
    os.makedirs(os.path.dirname(GEO_CACHE_FILE), exist_ok=True)
    try:
        with open(GEO_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except:
        pass

def reverse_geocode_coords(lat: str, lon: str) -> Optional[Dict[str, str]]:
    """
    Reverse geocodes coordinate values to extract district, city, town, local_area, state, and pincode.
    Uses OpenStreetMap (Nominatim) API and caches responses locally.
    """
    if not lat or not lon:
        return None
    try:
        lat_f = float(str(lat).strip())
        lon_f = float(str(lon).strip())
        if abs(lat_f) < 0.1 or abs(lon_f) < 0.1:
            return None
    except ValueError:
        return None
        
    # Round to 5 decimal places (~1.1 meter precision) to cache efficiently
    cache_key = f"{lat_f:.5f},{lon_f:.5f}"
    
    cache = load_geo_cache()
    if cache_key in cache:
        return cache[cache_key]
        
    # Respect Nominatim API limits: wait 1 second
    time.sleep(1.0)
    
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat_f}&lon={lon_f}&zoom=18&addressdetails=1"
    headers = {
        "User-Agent": "JustDialScraperLocationCorrector/1.0"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            address = data.get("address", {})
            
            district = address.get("state_district") or address.get("county") or ""
            state = address.get("state") or ""
            
            # Clean district suffix
            if district.endswith(" District"):
                district = district[:-9]
                
            town = address.get("town") or address.get("city") or address.get("municipality") or address.get("village") or ""
            local_area = address.get("suburb") or address.get("neighbourhood") or address.get("city_district") or address.get("village") or address.get("hamlet") or ""
            pincode = address.get("postcode") or ""
            
            result = {
                "district": district,
                "state": state,
                "town": town,
                "local_area": local_area,
                "pincode": pincode
            }
            
            cache[cache_key] = result
            save_geo_cache(cache)
            return result
    except Exception as e:
        print(f"Error calling reverse geocoder: {e}")
        
    return None

def upload_to_db_directly(listing: Dict, district: str, main_cat: str = "") -> bool:
    from app.database import SessionLocal
    from app import models
    from datetime import datetime
    import time
    
    db = SessionLocal()
    try:
        name = listing["name"]
        phone = listing.get("phone", "")
        address = listing.get("address", "")
        source_url = listing.get("source_url", "")
        if not source_url:
            source_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{name.replace(' ', '-')}"
        
        # If main_cat is supplied (e.g. "Restaurants"), use it as the canonical category
        # and put the JustDial cuisine tags (e.g. "Punjabi, South Indian") into subcategory.
        raw_category = listing.get("category", "")
        if main_cat:
            category = main_cat
            subcategory = raw_category  # JD tags become subcategory
        elif ">" in raw_category:
            parts = raw_category.split(">", 1)
            category = parts[0].strip()
            subcategory = parts[1].strip()
        else:
            # No main_cat: try to detect if raw_category looks like cuisine tags
            # (contains comma or known cuisine keywords) and set category to parent type
            cuisine_keywords = [
                "South Indian", "North Indian", "Punjabi", "Chinese", "Continental",
                "Mughlai", "Bengali", "Gujarati", "Rajasthani", "Kerala", "Udupi",
                "Multicuisine", "Fast Food", "Barbeque", "Buffet", "Sea Food", "Seafood",
                "Veg", "Non Veg", "Street Food", "Desserts", "Italian", "Thai", "Mexican"
            ]
            is_cuisine_tag = any(kw.lower() in raw_category.lower() for kw in cuisine_keywords)
            if is_cuisine_tag:
                category = "Restaurants"
                subcategory = raw_category
            else:
                category = raw_category
                subcategory = listing.get("subcategory", "")
        
        latitude = listing.get("latitude", "")
        longitude = listing.get("longitude", "")
        opening_hours = listing.get("opening_hours", "")
        
        # Hybrid Location Engine: Try Coordinate Reverse Geocoding first, fallback to address text parsing
        geo_info = reverse_geocode_coords(latitude, longitude)
        if geo_info:
            if geo_info.get("district"):
                district = geo_info["district"]
            state = geo_info.get("state") or listing.get("state", "") or get_state_from_district(district)
            
            # Construct place value
            town_val = geo_info.get("town") or ""
            local_val = geo_info.get("local_area") or ""
            if local_val and town_val and local_val.lower() != town_val.lower():
                place = f"{local_val}, {town_val}"
            else:
                place = local_val or town_val
        else:
            # Overwrite district with one found in address if any
            addr_district = extract_district_from_address(address)
            if addr_district:
                district = addr_district
                
            # Auto-assign state from district
            state = listing.get("state", "") or get_state_from_district(district)
            
            # Extract specific locality/place from address (e.g. Kuttikkanam from 'Kuttikkanam, Idukki')
            place = extract_place_from_address(address, district)
        
        # Detect if business name contains building/complex keywords
        # e.g. 'Maryam Trade Center' -> category='Trade Centers'
        if not main_cat:  # only auto-detect if no main_cat was explicitly passed
            category = detect_category_from_name(name, category)
        
        existing = db.query(models.Listing).filter(models.Listing.name == name).first()
        if existing:
            listing_obj = existing
            listing_obj.phone = phone or existing.phone
            listing_obj.address = address or existing.address
            listing_obj.category = category or existing.category
            listing_obj.subcategory = subcategory or existing.subcategory
            listing_obj.district = district or existing.district
            listing_obj.place = place or existing.place
            listing_obj.state = state or existing.state
            listing_obj.latitude = latitude or existing.latitude
            listing_obj.longitude = longitude or existing.longitude
            listing_obj.opening_hours = opening_hours or existing.opening_hours
            listing_obj.scraped_at = datetime.utcnow()
        else:
            listing_obj = models.Listing(
                name=name,
                phone=phone,
                address=address,
                jd_url=source_url,
                category=category,
                subcategory=subcategory,
                district=district,
                place=place,
                state=state,
                latitude=latitude,
                longitude=longitude,
                opening_hours=opening_hours
            )
            db.add(listing_obj)
            db.flush()
            
        # Add all images
        images = listing.get("images", [])
        for idx, img_path in enumerate(images):
            img_exists = db.query(models.ListingImage).filter(
                models.ListingImage.listing_id == listing_obj.id,
                models.ListingImage.image_path == img_path
            ).first()
            if not img_exists:
                db.add(models.ListingImage(
                    listing_id=listing_obj.id,
                    image_path=img_path,
                    category="general",
                    is_primary=(idx == 0)
                ))
                
        db.commit()
        return True
    except Exception as e:
        print(f"Direct DB save error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def process_emulator_json(json_data: Any, district: str = "Unknown", main_cat: str = "") -> int:
    """
    Parses intercepted JSON from the JustDial mobile app API and uploads 
    to our database. Returns the number of successfully uploaded listings.
    """
    if isinstance(json_data, dict) and "json_data" in json_data:
        district = json_data.get("district", district) or district
        if not main_cat:
            main_cat = json_data.get("main_cat", "") or ""
        json_data = json_data["json_data"]

    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            log("❌ Invalid JSON string provided to emulator parser.", ok=False)
            return 0
    else:
        data = json_data

    listings = []

    # Check if this is a HAR file export from HTTP Toolkit
    if "log" in data and "entries" in data["log"]:
        log("📦 Detected a full HAR file export. Scanning all requests...")
        success_count = 0
        for entry in data["log"]["entries"]:
            # Get the response text
            try:
                content_text = entry.get("response", {}).get("content", {}).get("text", "")
                if content_text and "results" in content_text:
                    # Attempt to parse this specific request's JSON
                    parsed_content = json.loads(content_text)
                    success_count += process_emulator_json(parsed_content, district)
            except Exception:
                pass
        return success_count

    # Parse standard mobile API format
    try:
        if "results" in data and isinstance(data["results"], dict) and "name" in data["results"]:
            # Single object format (e.g. detailed view)
            res = data["results"]
            parsed_res = {
                "name": res.get("name", ""),
                "phone": clean_phone(res.get("mobile", "")),
                "rating": res.get("rating", ""),
                "review_count": res.get("totJdReviews", ""),
                "address": res.get("address", ""),
                "thumbnail": res.get("jadoopic", ""),
                "latitude": res.get("complat", ""),
                "longitude": res.get("complong", ""),
                "url": res.get("Sharerating", "").strip()
            }
            if parsed_res["name"]:
                listings.append(parsed_res)
            log(f"📱 Emulator Parser found format: Single Object")
            
        elif "results" in data and "columns" in data["results"] and "data" in data["results"]:
            # Array format (e.g. search list)
            columns = data["results"]["columns"]
            rows = data["results"]["data"]
            log(f"📱 Emulator Parser found format: {len(columns)} columns, {len(rows)} rows")
            
            col_map = {col: i for i, col in enumerate(columns)}
            
            for row in rows:
                if not isinstance(row, list):
                    continue
                r = parse_api_row(row, col_map)
                if r:
                    listings.append(r)
    except Exception as e:
        log(f"❌ Error parsing emulator JSON: {e}", ok=False)
        return 0

    if not listings:
        log("⚠️ No listings found in the provided JSON.", ok=False)
        return 0

    log(f"📱 Extracted {len(listings)} listings from JSON. Uploading...")
    
    success_count = 0
    for res in listings:
        name = res.get("name", "Unknown")
        phone = res.get("phone", "")
        rating = res.get("rating", "")
        
        log(f"  ➜ {name} | Phone: {phone} | Rating: {rating}")
        
        if upload_to_db_directly(res, district, main_cat=main_cat):
            success_count += 1
            log(f"    Uploaded!")
        else:
            log(f"    Failed.", ok=False)

    log(f"Emulator JSON Processing Complete: {success_count}/{len(listings)} uploaded successfully.")
    return success_count
