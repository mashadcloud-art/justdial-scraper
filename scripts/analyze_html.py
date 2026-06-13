from bs4 import BeautifulSoup
import re

# Read the debug HTML
with open('debug_page.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

print("=== ANALYZING JUSTDIAL PAGE STRUCTURE ===\n")

# Find all headings (potential names)
print("📝 HEADINGS (potential names):")
for h in soup.find_all(['h1', 'h2', 'h3'])[:10]:
    print(f"  <{h.name} class='{h.get('class')}'> {h.get_text(strip=True)[:50]}")

# Find phone patterns
print("\n📞 PHONE NUMBERS:")
phone_pattern = re.compile(r'(\+?\d{10,15})')
for elem in soup.find_all(string=phone_pattern):
    parent = elem.parent
    print(f"  Found: {elem.strip()} in <{parent.name} class='{parent.get('class')}'>")

# Find address patterns
print("\n📍 ADDRESS ELEMENTS:")
for elem in soup.find_all(string=re.compile(r'(Road|Street|Area|Mumbai|Kerala)', re.I)):
    parent = elem.parent
    if len(elem.strip()) > 10:
        print(f"  <{parent.name} class='{parent.get('class')}'> {elem.strip()[:80]}")

# Find images
print("\n🖼️ IMAGES:")
for img in soup.find_all('img')[:10]:
    src = img.get('data-src') or img.get('src')
    if src and 'justdial' in src:
        print(f"  <img class='{img.get('class')}'> src={src[:80]}")

# Find opening hours
print("\n⏰ OPENING HOURS:")
for elem in soup.find_all(string=re.compile(r'(AM|PM|Open|Close|Hour)', re.I)):
    parent = elem.parent
    if len(elem.strip()) > 5:
        print(f"  <{parent.name} class='{parent.get('class')}'> {elem.strip()[:80]}")