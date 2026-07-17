import json
from collections import Counter

with open('data/pincodes.json', 'r') as f:
    data = json.load(f)

# Show taluks for each Kerala district
kerala_districts = [
    'Thiruvananthapuram','Kollam','Pathanamthitta','Alappuzha','Kottayam',
    'Idukki','Ernakulam','Thrissur','Palakkad','Malappuram',
    'Kozhikode','Wayanad','Kannur','Kasaragod'
]

for district in kerala_districts:
    pins = [p for p in data if district.lower() in str(p.get('districtName','')).lower()]
    taluks = Counter(p.get('taluk','') for p in pins)
    print(f"\n{district} ({len(pins)} pincodes) — Taluks:")
    for taluk, count in sorted(taluks.items(), key=lambda x: -x[1]):
        print(f"  {taluk}: {count}")
