import json
import logging
import requests
from mitmproxy import http
import os
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - MITM - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

backend_url = "http://127.0.0.1:8000"
try:
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            if cfg and "api" in cfg and "backend_url" in cfg["api"]:
                backend_url = cfg["api"]["backend_url"]
                logger.info(f"Loaded backend_url from config: {backend_url}")
except Exception as e:
    logger.error(f"Error loading config.yaml: {e}")

INGEST_URL = f"{backend_url.rstrip('/')}/api/v1/ingest-emulator-json"
# Also always send to localhost for local DB
LOCAL_INGEST_URL = "http://127.0.0.1:8000/api/v1/ingest-emulator-json"

JUSTDIAL_DOMAINS = ["justdial.com", "jdmagicbox.com"]

# Save raw JSON for debugging
DUMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "captured_json")
os.makedirs(DUMP_DIR, exist_ok=True)

capture_count = 0

def response(flow: http.HTTPFlow):
    global capture_count
    url = flow.request.url

    if not any(d in url for d in JUSTDIAL_DOMAINS):
        return
    if not flow.response:
        return

    content_type = flow.response.headers.get("Content-Type", "")
    logger.info(f"[JD] {flow.request.method} {url[:100]} -> {flow.response.status_code} | CT: {content_type[:40]}")

    try:
        body = flow.response.get_text()
        if not body or len(body) < 50:
            return

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return

        # Save searchziva JSON for analysis
        if "searchziva" in url:
            capture_count += 1
            fname = os.path.join(DUMP_DIR, f"searchziva_{capture_count}.json")
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"SAVED searchziva JSON to {fname} ({len(body)} bytes)")

        # Detect if this is search result data
        found = False
        rows = []

        if isinstance(data, dict):
            # Format 1: {"results": {"columns": [...], "data": [[...], ...]}} — main JD format
            if "results" in data and isinstance(data.get("results"), dict):
                inner = data["results"]
                if "data" in inner and isinstance(inner["data"], list):
                    rows = inner["data"]
                    found = True
            # Format 2: {"data": [...]}
            elif "data" in data and isinstance(data.get("data"), list) and len(data["data"]) > 0:
                rows = data["data"]
                found = True
            # Format 3: any key with list of dicts
            else:
                for key, val in data.items():
                    if isinstance(val, list) and len(val) > 2:
                        if all(isinstance(item, (dict, list)) for item in val[:3]):
                            rows = val
                            found = True
                            break
        elif isinstance(data, list) and len(data) > 0:
            rows = data
            found = True

        if found and len(rows) > 0:
            logger.info(f"INTERCEPTED! {len(rows)} items from {url[:80]}")
            
            # Extract district from URL if possible
            district = "Auto"
            if "city=" in url:
                import re
                m = re.search(r"city=([^&]+)", url)
                if m:
                    district = m.group(1)
            
            payload = {
                "json_data": body,
                "state": "Auto",
                "district": district,
                "category": "Auto",
                "subcategory": "Auto"
            }

            # Send to LOCAL backend first
            try:
                res = requests.post(LOCAL_INGEST_URL, json=payload, timeout=10)
                if res.status_code == 200:
                    parsed_res = res.json()
                    ext_count = parsed_res.get("count", parsed_res.get("extracted_count", 0))
                    logger.info(f"LOCAL SUCCESS: Ingested {ext_count} businesses!")
                else:
                    logger.error(f"LOCAL failed. Status: {res.status_code} Body: {res.text[:200]}")
            except Exception as req_err:
                logger.error(f"LOCAL send error (backend not running?): {req_err}")

            # Also send to REMOTE backend
            if INGEST_URL != LOCAL_INGEST_URL:
                try:
                    res = requests.post(INGEST_URL, json=payload, timeout=10)
                    if res.status_code == 200:
                        parsed_res = res.json()
                        ext_count = parsed_res.get("count", parsed_res.get("extracted_count", 0))
                        logger.info(f"REMOTE SUCCESS: Ingested {ext_count} businesses!")
                    else:
                        logger.error(f"REMOTE failed. Status: {res.status_code} Body: {res.text[:200]}")
                except Exception as req_err:
                    logger.error(f"REMOTE send error: {req_err}")

    except Exception as e:
        logger.error(f"Error processing: {e}")
