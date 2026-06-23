import requests
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
r = requests.get('https://www.justdial.com/Thiruvananthapuram/Restaurants', headers=headers)
with open('requests_page.html', 'w', encoding='utf-8') as f:
    f.write(r.text)
