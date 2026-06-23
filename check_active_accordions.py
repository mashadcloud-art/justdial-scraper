from bs4 import BeautifulSoup
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("jithu_joji_menu_clicked.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

print("=== Checking accordion items and their classes ===")
accordion_items = soup.find_all(class_=lambda c: c and "accordion_item" in c)
print(f"Total accordion items: {len(accordion_items)}")
for idx, item in enumerate(accordion_items):
    classes = item.get("class", [])
    title_el = item.find(class_=lambda c: c and "accordion_button" in c)
    title = title_el.get_text(strip=True) if title_el else "No Title"
    print(f"Item {idx}: Title: {title} | Classes: {classes}")
