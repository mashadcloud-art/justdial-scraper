
from bs4 import BeautifulSoup
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open("specific_menu_page.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

service_rows = soup.find_all(attrs={"class": re.compile(r"service_row")})

for i, row in enumerate(service_rows, 1):
    print(f"\n=== Row {i} ===")
    try:
        print("HTML Preview:", str(row)[:800])
    except:
        print("Couldn't print HTML preview")
    print("\nText:", row.get_text(strip=True))
    
    # Find price element
    price_el = row.find(attrs={"class": re.compile(r"service_priceoffer")})
    if price_el:
        print("Price Text:", price_el.get_text(strip=True))
