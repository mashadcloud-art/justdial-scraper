import requests
import json

url = "https://www.justdial.com/webmain/wrap-app.php"

headers = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "origin": "https://www.justdial.com",
    "referer": "https://www.justdial.com/Kasaragod/Restaurants/nct-10408936",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0"
}

files = {
    "prm": (None, "/01sep2022/ads.php?case=filter&entity=89|15234&city=kasaragod&area=&search=Restaurants&apiname=Filterapi&dpf=8796227240448&wap=77&version=3.0&ln=&is_rsltpg=1"),
    "cs": (None, "fltr")
}

try:
    r = requests.post(url, headers=headers, files=files, timeout=10)
    data = r.json()
    with open("wrap-app.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Keys:", list(data.keys()))
    if 'results' in data and isinstance(data['results'], dict):
        print("results keys:", list(data['results'].keys()))
    print("Wrote full response to wrap-app.json")
except Exception as e:
    print("Error:", e)
