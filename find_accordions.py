from bs4 import BeautifulSoup
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("jithu_joji_menu_clicked.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

print("=== Looking for buttons / accordions ===")
for btn in soup.find_all(["button", "a", "span", "div"]):
    text = btn.get_text(strip=True)
    classes = " ".join(btn.get("class", [])) if btn.get("class") else ""
    if any(x in text.lower() for x in ["view all", "more", "expand", "show all"]) or any(x in classes.lower() for x in ["accordion", "viewall", "expand"]):
        if len(text) < 100:
            print(f"Tag: {btn.name}, Class: {classes}, Text: {text}")

print("\n=== Checking scrollable containers ===")
# Some JD pages have scrollable menu categories
for el in soup.find_all(True):
    style = el.get("style", "")
    if "overflow" in style or "scroll" in style:
        print(f"Tag: {el.name}, Class: {el.get('class')}, Style: {style}, Text preview: {el.get_text(strip=True)[:100]}")
