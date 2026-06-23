import sys
import os
import json
import requests

def upload_har(har_path: str, district: str):
    if not os.path.exists(har_path):
        print(f"❌ Error: File not found at '{har_path}'")
        return

    print(f"📖 Reading HAR file: {har_path} ...")
    try:
        with open(har_path, 'r', encoding='utf-8') as f:
            har_data = json.load(f)
    except Exception as e:
        print(f"❌ Error: Failed to parse HAR file as JSON. {e}")
        return

    # Check if it looks like a HAR file
    if "log" not in har_data or "entries" not in har_data["log"]:
        print("⚠️ Warning: The JSON does not look like a standard HAR structure, but we will send it anyway.")

    url = "http://127.0.0.1:8000/api/sync/ingest-emulator-json"
    params = {"district": district}
    
    print(f"🚀 Uploading data to backend ({url}) for district '{district}'...")
    try:
        response = requests.post(url, params=params, json=har_data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                print(f"✅ Success! {result.get('message')}")
                print(f"📊 Total new records added: {result.get('count', 0)}")
            else:
                print(f"❌ Backend returned error: {result.get('message')}")
        else:
            print(f"❌ HTTP request failed with status code {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python upload_har.py <path_to_har_file> [district_name]")
        print("Example: python upload_har.py C:\\Users\\PC\\Downloads\\justdial.har Kasaragod")
        sys.exit(1)
        
    path = sys.argv[1]
    dist = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
    upload_har(path, dist)
