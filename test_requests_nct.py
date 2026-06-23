import requests
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
url = "https://www.justdial.com/Thiruvananthapuram/Restaurants/nct-10408936"
print("Fetching:", url)
try:
    r = requests.get(url, headers=headers, timeout=10)
    print("Status:", r.status_code)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, 'html.parser')
    next_data = soup.find('script', id='__NEXT_DATA__')
    if next_data:
        print("Found __NEXT_DATA__")
    else:
        print("No __NEXT_DATA__")
except Exception as e:
    print("Error:", e)
