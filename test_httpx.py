import httpx
import json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1'
}

url = "https://www.justdial.com/Thiruvananthapuram/Restaurants/nct-10408936"
print("Trying httpx:", url)

try:
    with httpx.Client(http2=True, headers=headers, follow_redirects=True) as client:
        r = client.get(url, timeout=10)
        print("Status:", r.status_code)
        if r.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            next_data = soup.find('script', id='__NEXT_DATA__')
            if next_data:
                print("Magic! found __NEXT_DATA__")
            else:
                print("No magic.")
except Exception as e:
    print("Error:", e)
