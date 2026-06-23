from curl_cffi import requests
from bs4 import BeautifulSoup
import json

url = "https://www.justdial.com/Thiruvananthapuram/Restaurants/nct-10408936"
print("Trying curl_cffi with chrome impersonation:", url)

try:
    r = requests.get(url, impersonate="chrome", timeout=10)
    print("Status:", r.status_code)
    
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        next_data = soup.find('script', id='__NEXT_DATA__')
        if next_data:
            print("Magic! found __NEXT_DATA__")
            data = json.loads(next_data.string)
            count = data.get("props", {}).get("pageProps", {}).get("searchResultData", {}).get("data", {}).get("totalNumberofResults")
            print("Count:", count)
        else:
            print("No __NEXT_DATA__ found. Response length:", len(r.text))
except Exception as e:
    print("Error:", e)
