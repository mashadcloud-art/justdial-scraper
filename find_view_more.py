from bs4 import BeautifulSoup
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("jithu_joji_menu_clicked.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

for el in soup.find_all(True):
    text = el.get_text(strip=True)
    if "View More" in text and len(text) < 50:
        print(f"Tag: {el.name}, Class: {el.get('class')}, Parent: {el.parent.name}.{'.'.join(el.parent.get('class', [])) if el.parent.get('class') else ''}")
