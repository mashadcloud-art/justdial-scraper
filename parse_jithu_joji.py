import re
import sys
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

print("=== Analyzing Menu in jithu_joji_menu_clicked.html ===")
with open("jithu_joji_menu_clicked.html", "r", encoding="utf-8") as f:
    menu_html = f.read()

soup_menu = BeautifulSoup(menu_html, "html.parser")

# Let's search for "veg" or "chicken" or "beef" or price symbol "₹" to find where the menu items are
items_with_rupee = []
for el in soup_menu.find_all(string=re.compile("₹")):
    parent = el.parent
    items_with_rupee.append(parent)

print(f"Found {len(items_with_rupee)} elements containing '₹'")
for idx, el in enumerate(items_with_rupee[:30]):
    print(f"\nItem {idx}:")
    print("  Tag:", el.name)
    print("  Class:", el.get("class"))
    print("  Text:", el.get_text(strip=True))
    # Print ancestors classes
    ancestors = []
    p = el.parent
    while p and len(ancestors) < 5:
        ancestors.append(f"{p.name}.{'.'.join(p.get('class', []))}")
        p = p.parent
    print("  Ancestors:", " -> ".join(ancestors))

print("\n=== Analyzing Gallery in jithu_joji_gallery.html ===")
with open("jithu_joji_gallery.html", "r", encoding="utf-8") as f:
    gallery_html = f.read()

soup_gallery = BeautifulSoup(gallery_html, "html.parser")
images = soup_gallery.find_all("img")
print(f"Found {len(images)} total images in gallery HTML")

jdmagic_images = [img for img in images if (img.get("src") and "jdmagicbox.com" in img.get("src")) or (img.get("data-src") and "jdmagicbox.com" in img.get("data-src"))]
print(f"Found {len(jdmagic_images)} jdmagicbox images")

for idx, img in enumerate(jdmagic_images[:30]):
    src = img.get("src") or img.get("data-src")
    print(f"\nImage {idx}:")
    print("  Src:", src)
    # Print parent structure
    ancestors = []
    p = img.parent
    is_similar = False
    while p:
        class_str = " ".join(p.get("class", [])) if p.get("class") else ""
        id_str = p.get("id", "") or ""
        tracker_str = p.get("data-tracker-id", "") or ""
        combined = f"{p.name}#{id_str}.{class_str}[tracker={tracker_str}]"
        ancestors.append(combined)
        if any(x in f"{id_str} {class_str} {tracker_str}".lower() for x in ['similar', 'suggest', 'recom', 'related', 'sponsored', 'people_also', 'popular', 'comp-ad', 'sidebar', 'footer']):
            is_similar = True
        p = p.parent
    print("  Is similar/related (according to current rule):", is_similar)
    print("  Ancestry (first 4):", " -> ".join(ancestors[:4]))
