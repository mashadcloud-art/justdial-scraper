import requests
from bs4 import BeautifulSoup
url = "https://www.justdial.com/Thiruvananthapuram"
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(url, headers=headers, timeout=10)
print(response.status_code)
soup = BeautifulSoup(response.text, 'html.parser')
sections = soup.find_all(['div', 'section'], class_=lambda x: x and ('category' in x.lower() or 'popular' in x.lower()))
print(len(sections))
