import requests
from bs4 import BeautifulSoup
r = requests.get('https://www.justdial.com/Kasaragod/Fast-Food', headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(r.text, 'html.parser')
links = [a.get('href') for a in soup.find_all('a', href=True) if 'page-' in a.get('href')]
print("Pagination links found:")
for link in links:
    print(link)
