import os
import json
import requests
import re
from config import settings

PINCODES_URL = "https://raw.githubusercontent.com/mithunsasidharan/India-Pincode-Lookup/master/pincodes.json"
CACHE_FILE = os.path.join(settings.DATA_FOLDER, "pincodes.json")

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

try:
    from fastapi import APIRouter
    router = APIRouter(prefix="/api/v1/pincodes", tags=["pincodes"])
except ImportError:
    # Dummy router for headless mode (no API server)
    class DummyRouter:
        def get(self, *args, **kwargs):
            return lambda f: f
    router = DummyRouter()

@router.get("/famous-places")
def get_famous_places(district: str):
    """
    Returns a curated list of famous places for a given district.
    """
    # Simple hardcoded dict for Kerala districts
    # Expanded list for Kerala districts
    places = {
        "thiruvananthapuram": ["Kovalam", "Varkala", "Technopark", "Pattom", "Kazhakootam", "Neyyattinkara", "Attingal", "Palayam", "Sasthamangalam", "Kowdiar", "Thampanoor", "East Fort", "Vazhuthacaud", "Sreekaryam", "Vattiyoorkavu", "Nemom", "Nedumangad", "Kattakada"],
        "kollam": ["Karunagappally", "Kottarakkara", "Punalur", "Paravur", "Sasthamcotta", "Chinnakada", "Chathannoor", "Kundara", "Pathanapuram", "Oachira", "Kottiyam"],
        "pathanamthitta": ["Adoor", "Thiruvalla", "Ranni", "Mallappally", "Kozhencherry", "Konni", "Pandalam", "Pathanamthitta Town"],
        "alappuzha": ["Kuttanad", "Chengannur", "Mavelikkara", "Cherthala", "Ambalappuzha", "Haripad", "Kayamkulam", "Aroor", "Edathua", "Alappuzha Town"],
        "kottayam": ["Pala", "Changanassery", "Vaikom", "Kanjirappally", "Ettumanoor", "Kottayam Town", "Kanjikuzhy", "Kanjirappally", "Ponkunnam", "Erattupetta", "Kuravilangad"],
        "idukki": ["Munnar", "Thodupuzha", "Adimali", "Kumily", "Nedumkandam", "Kattappana", "Peermade", "Devikulam", "Vagamon", "Idukki Township"],
        "ernakulam": ["Kochi", "Edappally", "Kakkanad", "Aluva", "Angamaly", "Perumbavoor", "Muvattupuzha", "Kothamangalam", "Tripunithura", "Vyttila", "Palarivattom", "Kaloor", "Marine Drive", "Fort Kochi", "Mattancherry", "Kalamassery", "Nedumbassery", "Piravom", "Koothattukulam", "North Paravur"],
        "thrissur": ["Chalakudy", "Irinjalakuda", "Guruvayur", "Kodungallur", "Kunnamkulam", "Wadakkanchery", "Thrissur Round", "Punkunnam", "Ayyanthole", "Kuriachira", "Ollur", "Mannuthy", "Chavakkad", "Triprayar", "Pudukkad"],
        "palakkad": ["Ottapalam", "Shornur", "Mannarkkad", "Chittur", "Pattambi", "Alathur", "Palakkad Town", "Kalpathy", "Malampuzha", "Walayar", "Vadakkencherry", "Nemmara"],
        "malappuram": ["Manjeri", "Tirur", "Ponnani", "Perinthalmanna", "Kottakkal", "Nilambur", "Malappuram Town", "Kondotty", "Edappal", "Valanchery", "Parappanangadi", "Tanur"],
        "kozhikode": ["Vadakara", "Koyilandy", "Thamarassery", "Feroke", "Ramanattukara", "Mukkam", "Kozhikode Beach", "SM Street", "Nadakkavu", "Mavoor Road", "Medical College", "Balussery", "Kunnamangalam", "Perambra"],
        "wayanad": ["Kalpetta", "Sulthan Bathery", "Mananthavady", "Vythiri", "Meenangadi", "Panamaram", "Pulpally", "Ambalavayal", "Meppadi", "Padinjarathara"],
        "kannur": ["Thalassery", "Payyanur", "Taliparamba", "Mattannur", "Iritty", "Kuthuparamba", "Kannur Town", "Payyambalam", "Chirakkal", "Pappinisseri", "Sreekandapuram", "Valapattanam", "Alakode"],
        "kasaragod": ["Kanhangad", "Uppala", "Trikaripur", "Nileshwar", "Cheruvathur", "Manjeshwar", "Kasaragod Town", "Badiyadka", "Kumbla", "Mulleria", "Udma", "Bekal"]
    }
    
    district_lower = district.lower().strip()
    return places.get(district_lower, [])

@router.get("/{district}")
def get_pincodes_with_names(district: str):
    """
    Returns pincodes and place names for a district.
    """
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            all_data = json.load(f)
            
        results = []
        seen_pins = set()
        search_district = district.lower().strip()
        
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
                name = str(item.get("officeName", ""))
                if pin and pin not in seen_pins:
                    seen_pins.add(pin)
                    # Clean up BO/SO/HO from place name
                    clean_name = re.sub(r'\s+(B\.O|S\.O|H\.O)$', '', name, flags=re.IGNORECASE)
                    results.append({"pin": pin, "name": clean_name})

        return results
    except Exception as e:
        print(f"Error reading pincodes: {e}")
        return []


def get_verified_place_names_for_district(district_name: str, category_hint: str = "Restaurants") -> list:
    """
    Returns deduplicated post-office place names for a district (sourced from the full
    India pincode database — typically 50-100+ per district, far more than the curated
    `get_famous_places` list). Each candidate is verified against a live JustDial search
    so obviously small/rural post offices that JustDial has no results for are dropped.

    Result is cached to disk since verification makes one live request per candidate place.
    """
    cache_path = os.path.join(settings.DATA_FOLDER, f"verified_places_{district_name.lower().strip().replace(' ', '_')}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if cached:
                    return cached
        except Exception:
            pass

    raw_places = get_pincodes_with_names(district_name)
    seen = set()
    candidates = []
    for item in raw_places:
        name = str(item.get("name", "")).strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        candidates.append(name)

    if not candidates:
        return []

    from jd_api_scraper import scrape_jd_api
    verified = []
    for place in candidates:
        try:
            result = scrape_jd_api(district_name, f"{category_hint} in {place}", limit=1)
            if result.get("rows"):
                verified.append(place)
        except Exception:
            continue

    result_list = verified if verified else candidates

    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result_list, f)
    except Exception:
        pass

    return result_list
