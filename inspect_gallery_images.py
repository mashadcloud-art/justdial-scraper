from bs4 import BeautifulSoup
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("jithu_joji_gallery.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
images = soup.find_all("img")
print(f"Total images in gallery: {len(images)}")

for idx, img in enumerate(images):
    src = img.get("src") or img.get("data-src") or ""
    if not src:
        continue
    
    # Check parents
    parents_info = []
    p = img.parent
    is_blocked = False
    while p:
        class_str = " ".join(p.get("class", [])) if p.get("class") else ""
        id_str = p.get("id", "") or ""
        tracker_str = p.get("data-tracker-id", "") or ""
        parents_info.append(f"{p.name}#{id_str}.{class_str}[tracker={tracker_str}]")
        if any(x in f"{id_str} {class_str} {tracker_str}".lower() for x in ['similar', 'suggest', 'recom', 'related', 'sponsored', 'people_also', 'popular', 'comp-ad', 'sidebar', 'footer']):
            is_blocked = True
        p = p.parent
        
    print(f"\nImage {idx}:")
    print(f"  Src: {src}")
    print(f"  Blocked by current rule: {is_blocked}")
    print(f"  Ancestry (first 5): {' -> '.join(parents_info[:5])}")
