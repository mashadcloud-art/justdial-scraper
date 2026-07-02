import os
import json
import requests

PINCODES_URL = "https://raw.githubusercontent.com/mithunsasidharan/India-Pincode-Lookup/master/pincodes.json"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "pincodes.json")

def get_pincodes_for_district(district_name: str):
    """
    Fetches pincodes for a specific district. Caches the full India database locally.
    """
    # Self-healing: if file exists but is invalid JSON (e.g., contains 404 HTML), delete it
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                json.load(f)
        except Exception:
            print("Cached pincodes.json is corrupted or invalid. Deleting to trigger re-download...")
            try:
                os.remove(CACHE_FILE)
            except Exception as e:
                print(f"Failed to delete corrupted pincodes file: {e}")

    if not os.path.exists(CACHE_FILE):
        print("Downloading India Pincodes database...")
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        try:
            res = requests.get(PINCODES_URL, timeout=30)
            if res.status_code == 200:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(res.text)
            else:
                print(f"Failed to download pincodes, status code: {res.status_code}")
                return []
        except Exception as e:
            print(f"Failed to download pincodes: {e}")
            return []

    if not os.path.exists(CACHE_FILE):
        return []

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            all_data = json.load(f)
            
        district_pins = []
        search_district = district_name.lower().strip()
        
        # Normalize common spelling variations to match database names
        normalization_map = {
            "kasaragod": "kasargod",
            "alleppey": "alappuzha",
            "trivandrum": "thiruvananthapuram",
            "trichur": "thrissur",
            "calicut": "kozhikode"
        }
        search_district = normalization_map.get(search_district, search_district)

        for item in all_data:
            d_name = str(item.get("districtName", "")).lower().strip()
            if search_district in d_name:
                pin = str(item.get("pincode", ""))
                if pin and pin not in district_pins:
                    district_pins.append(pin)
                    
        return district_pins
    except Exception as e:
        print(f"Error reading pincodes: {e}")
        return []

