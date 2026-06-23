from bs4 import BeautifulSoup
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("jithu_joji_menu_clicked.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

service_rows = soup.find_all(attrs={"class": re.compile(r"service_row")})
print(f"Total service_rows found: {len(service_rows)}")

seen = set()
menu_items = []
for idx, row in enumerate(service_rows):
    name_el = row.find(attrs={"class": re.compile(r"service_name")})
    if not name_el:
        print(f"Row {idx} missing name element. Class list: {row.get('class')}")
        continue
    item_name = name_el.get_text(strip=True)
    
    price = "0"
    price_el = row.find(attrs={"class": re.compile(r"service_priceoffer")})
    if price_el:
        price_text = price_el.get_text(strip=True)
        price_match = re.search(r'(\d+)', price_text)
        if price_match:
            price = price_match.group(1)
            
    is_veg = True
    tagbox = row.find(attrs={"class": re.compile(r"service_tagbox")})
    if tagbox:
        img = tagbox.find('img')
        if img:
            alt = img.get('alt', '').lower()
            src = img.get('src', '').lower()
            if 'non' in alt or 'non' in src or 'egg' in alt or 'egg' in src:
                is_veg = False
                
    print(f"{idx}: {item_name} | Price: {price} | Veg: {is_veg}")
