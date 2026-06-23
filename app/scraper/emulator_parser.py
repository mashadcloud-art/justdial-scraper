import json
import os
import re
import requests
from typing import List, Dict, Any
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
    "Karandakkad", "Padanakkad", "Poinachi", "Kanhangad", "Nileshwar",
    "Adkathbail", "Panathur", "Kasaragod",
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

def extract_place_from_address(address: str, district: str) -> str:
    """
    Extracts the specific locality/place from address.
    e.g. 'Kuttikkanam, Idukki' -> 'Kuttikkanam'
         'Maryam Trade Center Adkathbail, Kasaragod' -> 'Adkathbail'
    """
    if not address:
        return ""
    
    # First try to match known Kerala places
    addr_lower = address.lower()
    for place in KERALA_PLACES:
        if place.lower() in addr_lower:
            return place
    
    # Fallback: split by comma, take the last word of the first segment
    parts = address.split(",")
    if len(parts) >= 2:
        # The locality is typically the last word before the district comma
        locality_segment = parts[-2].strip() if len(parts) >= 2 else parts[0].strip()
        # Take last word (often the place name comes after building/street names)
        words = locality_segment.split()
        if words:
            candidate = words[-1].strip()
            # Don't use district name as place
            if candidate.lower() != (district or "").lower() and len(candidate) > 2:
                return candidate
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

def upload_to_db_directly(restaurant: Dict, district: str, main_cat: str = "") -> bool:
    from app.database import SessionLocal
    from app import models
    from datetime import datetime
    
    db = SessionLocal()
    try:
        name = restaurant["name"]
        phone = restaurant.get("phone", "")
        address = restaurant.get("address", "")
        source_url = restaurant.get("source_url", "")
        if not source_url:
            source_url = f"https://www.justdial.com/{district.replace(' ', '-')}/{name.replace(' ', '-')}"
        
        # If main_cat is supplied (e.g. "Restaurants"), use it as the canonical category
        # and put the JustDial cuisine tags (e.g. "Punjabi, South Indian") into subcategory.
        raw_category = restaurant.get("category", "")
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
                subcategory = restaurant.get("subcategory", "")
        
        latitude = restaurant.get("latitude", "")
        longitude = restaurant.get("longitude", "")
        opening_hours = restaurant.get("opening_hours", "")
        
        # Auto-assign state from district
        state = restaurant.get("state", "") or get_state_from_district(district)
        
        # Extract specific locality/place from address (e.g. Kuttikkanam from 'Kuttikkanam, Idukki')
        place = extract_place_from_address(address, district)
        
        # Detect if business name contains building/complex keywords
        # e.g. 'Maryam Trade Center' -> category='Trade Centers'
        if not main_cat:  # only auto-detect if no main_cat was explicitly passed
            category = detect_category_from_name(name, category)
        
        existing = db.query(models.Restaurant).filter(models.Restaurant.name == name).first()
        if existing:
            restaurant_obj = existing
            restaurant_obj.phone = phone or existing.phone
            restaurant_obj.address = address or existing.address
            restaurant_obj.category = category or existing.category
            restaurant_obj.subcategory = subcategory or existing.subcategory
            restaurant_obj.district = district or existing.district
            restaurant_obj.place = place or existing.place
            restaurant_obj.state = state or existing.state
            restaurant_obj.latitude = latitude or existing.latitude
            restaurant_obj.longitude = longitude or existing.longitude
            restaurant_obj.opening_hours = opening_hours or existing.opening_hours
            restaurant_obj.scraped_at = datetime.utcnow()
        else:
            restaurant_obj = models.Restaurant(
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
            db.add(restaurant_obj)
            db.flush()
            
        # Add all images
        images = restaurant.get("images", [])
        for idx, img_path in enumerate(images):
            img_exists = db.query(models.RestaurantImage).filter(
                models.RestaurantImage.restaurant_id == restaurant_obj.id,
                models.RestaurantImage.image_path == img_path
            ).first()
            if not img_exists:
                db.add(models.RestaurantImage(
                    restaurant_id=restaurant_obj.id,
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
    to our database. Returns the number of successfully uploaded restaurants.
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

    restaurants = []

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
                restaurants.append(parsed_res)
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
                    restaurants.append(r)
    except Exception as e:
        log(f"❌ Error parsing emulator JSON: {e}", ok=False)
        return 0

    if not restaurants:
        log("⚠️ No restaurants found in the provided JSON.", ok=False)
        return 0

    log(f"📱 Extracted {len(restaurants)} restaurants from JSON. Uploading...")
    
    success_count = 0
    for res in restaurants:
        name = res.get("name", "Unknown")
        phone = res.get("phone", "")
        rating = res.get("rating", "")
        
        log(f"  ➜ {name} | Phone: {phone} | Rating: {rating}")
        
        if upload_to_db_directly(res, district, main_cat=main_cat):
            success_count += 1
            log(f"    Uploaded!")
        else:
            log(f"    Failed.", ok=False)

    log(f"Emulator JSON Processing Complete: {success_count}/{len(restaurants)} uploaded successfully.")
    return success_count
