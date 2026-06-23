import json
from app.scraper.emulator_parser import process_emulator_json

payload = {
  "status": 1,
  "fallbacksearch": "Restaurants",
  "search_id": "9a787250cfd620d1ea7e3483fcca65a8aa23ff11aded413b17bd798cf93b3e61"
}

print("Calling process_emulator_json directly...")
try:
    res = process_emulator_json(payload, "Thiruvananthapuram")
    print("Result (success_count):", res)
except Exception as e:
    import traceback
    traceback.print_exc()
