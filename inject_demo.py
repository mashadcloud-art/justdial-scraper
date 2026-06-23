import requests
import json

demo_json_string = """{
  "results": {
    "columns": ["docid", "name", "phone", "rating", "review_count", "address", "thumbnail", "latitude", "longitude"],
    "data": [
      ["12345", "Super Emulator Burger Joint", "+919876543210", "4.8", "120", "123 Test St, Ernakulam", "https://via.placeholder.com/150", "9.9", "76.2"],
      ["67890", "Mobile Magic Cafe", "+918765432109", "4.5", "85", "456 Mobile Ave, Kochi", "https://via.placeholder.com/150", "9.8", "76.3"]
    ]
  }
}"""

print("Injecting sample JSON directly into the backend...")
res = requests.post("http://127.0.0.1:8000/api/v1/ingest-emulator-json?district=Ernakulam", json={
    "json_data": demo_json_string
})
print("Response text:", res.text)
