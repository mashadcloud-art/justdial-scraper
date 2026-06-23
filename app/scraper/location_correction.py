from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time

# Initialize Nominatim API (OpenStreetMap)
# Important: Nominatim has a strict usage policy. We must provide a unique user_agent
# and limit requests to 1 per second.
geolocator = Nominatim(user_agent="justdial_pro_scraper_location_engine")

def reverse_geocode(lat, lon, retries=3):
    """Reverse geocodes lat/lon with retries."""
    for attempt in range(retries):
        try:
            # We must respect Nominatim limits: 1 request per second
            time.sleep(1)
            location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
            if not location:
                return None
            return location.raw.get('address', {})
        except GeocoderTimedOut:
            if attempt == retries - 1:
                return None
            time.sleep(2)
        except Exception as e:
            print(f"Reverse Geocoding Error: {e}")
            return None
    return None

def get_corrected_location(lat, lon, current_district=None, current_place=None):
    """
    Given a latitude and longitude, determines the correct location fields.
    Compares against current_district and current_place if provided.
    Returns a dictionary matching the user's expected output format.
    """
    if not lat or not lon:
        return {"corrected": False, "notes": "No latitude or longitude provided."}
        
    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return {"corrected": False, "notes": "Invalid latitude or longitude."}

    address = reverse_geocode(lat, lon)
    if not address:
        return {"corrected": False, "notes": "Reverse geocoding failed or returned no results."}
    
    # Extract location parts
    pincode = address.get('postcode', '')
    state = address.get('state', '')
    
    # City can be mapped from city / town / village / municipality
    city = address.get('city') or address.get('municipality') or address.get('town') or address.get('village') or ''
    
    # District mapping
    district = address.get('state_district', '')
    if district.endswith(' District'):
        district = district.replace(' District', '')
        
    # Area / Locality mapping
    area = address.get('suburb') or address.get('neighbourhood') or address.get('residential') or address.get('road') or ''
    
    # Default return structure
    result = {
        "corrected": False,
        "correct_district": district,
        "correct_city": city,
        "correct_area": area,
        "correct_pincode": pincode,
        "correct_state": state,
        "notes": ""
    }
    
    # Determine if a correction is actually needed
    is_wrong = False
    notes_list = []
    
    if current_district and district:
        if district.lower() not in current_district.lower() and current_district.lower() not in district.lower():
            is_wrong = True
            notes_list.append(f"District mismatch (found: {district}, current: {current_district})")
            
    if current_place and city:
        if city.lower() not in current_place.lower() and current_place.lower() not in city.lower():
            is_wrong = True
            notes_list.append(f"City/Place mismatch (found: {city}, current: {current_place})")
            
    if is_wrong:
        result["corrected"] = True
        result["notes"] = "; ".join(notes_list)
    else:
        result["notes"] = "Location looks correct based on coordinates."

    return result
