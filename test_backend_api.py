import requests
url = "http://127.0.0.1:8000/api/v1/listing-count?city=Thiruvananthapuram&category=Restaurants"
print("Fetching from backend:", url)
try:
    r = requests.get(url, timeout=30)
    print("Status:", r.status_code)
    print("Response:", r.text)
except Exception as e:
    print("Error:", e)
