"""
fetch_aster_hd_images.py
Scrapes high-resolution hospital banner/logo images from asterhospitals.in and saves them to aster_hospitals_details_hd.json.
"""
import requests
from bs4 import BeautifulSoup
import json
import os

INPUT_PATH = r"C:\Users\PC\Desktop\aster_hospitals_details.json"
OUTPUT_PATH = r"C:\Users\PC\Desktop\aster_hospitals_details_hd.json"

if not os.path.exists(INPUT_PATH):
    print(f"❌ Input file not found at {INPUT_PATH}")
    exit(1)

with open(INPUT_PATH, "r", encoding="utf-8-sig") as f:
    hospitals = json.load(f)

def get_high_res_image(hospital_name):
    slug_map = {
        "Aster Medcity": "aster-medcity-kochi",
        "Aster CMI Hospital": "aster-cmi-hospital-bangalore",
        "Aster MIMS Hospital, Calicut": "aster-mims-calicut",
        "Aster MIMS Hospital, Kannur": "aster-mims-kannur",
        "Aster MIMS Kottakkal": "aster-mims-kottakkal",
        "Aster Prime Hospital": "aster-prime-hospital-hyderabad",
        "Aster RV Hospital": "aster-rv-hospital-bangalore",
        "Aster Whitefield Hospital": "aster-whitefield-hospital-bangalore",
        "Aster Aadhar Hospital": "aster-aadhar-hospital-kolhapur",
        "Aster Mother Hospital, Areekode": "aster-mother-hospital-areekode"
    }
    
    slug = slug_map.get(hospital_name)
    if not slug:
        return None

    url = f"https://www.asterhospitals.in/hospitals/{slug}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Target meta tag og:image or banner img
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content') and og_img.get('content').startswith('http'):
                return og_img.get('content')
                
            img_tag = soup.find('img', class_='banner-img')
            if img_tag:
                src = img_tag.get('src')
                if src and src.startswith('http'):
                    return src
    except Exception as e:
        print(f"  Error fetching {hospital_name}: {e}")
    return None

print("🔍 Fetching high-resolution images for Aster Hospitals...")
for hospital in hospitals:
    print(f"Checking {hospital['name']}...")
    new_img = get_high_res_image(hospital['name'])
    if new_img:
        hospital['image_url'] = new_img
        hospital['image_url_hd'] = new_img
        print(f"  ✅ Found HD Image: {new_img}")
    else:
        print(f"  ⚠️ Keeping current image for {hospital['name']}")

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(hospitals, f, indent=2)

print(f"\n✅ Saved HD Hospital images to {OUTPUT_PATH}")
