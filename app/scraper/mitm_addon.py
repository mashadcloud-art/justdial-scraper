import json
import logging
import requests
from mitmproxy import http

import os
import yaml

# Set up logging for mitmproxy script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - MITM - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Dynamically load backend URL from config.yaml
backend_url = "http://127.0.0.1:8000"
try:
    # Try finding config.yaml in the working directory or parent directories
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
    logger.error(f"Error loading config.yaml in mitm_addon: {e}")

# Backend API to ingest the data
INGEST_URL = f"{backend_url.rstrip('/')}/api/v1/ingest-emulator-json"

def response(flow: http.HTTPFlow):
    """
    This function is automatically called by mitmproxy for every HTTP response.
    """
    # 1. Check if the URL is from JustDial and looks like an API call returning JSON
    if "justdial.com" in flow.request.url and flow.response:
        # Check if response is JSON
        content_type = flow.response.headers.get("Content-Type", "")
        if "application/json" in content_type or "text/json" in content_type or "application/javascript" in content_type:
            
            try:
                # Extract the body text
                body = flow.response.get_text()
                if not body:
                    return
                
                # Try to parse it to confirm it's valid JSON and contains what we want
                data = json.loads(body)
                
                # 2. Check if this JSON contains the 'results' -> 'data' structure
                if "results" in data and isinstance(data["results"], dict) and "data" in data["results"]:
                    rows = data["results"]["data"]
                    if len(rows) > 0:
                        logger.info(f"🚀 INTERCEPTED! Found JustDial API response with {len(rows)} restaurants.")
                        
                        # 3. Send it silently to our FastAPI backend!
                        payload = {
                            "json_data": body,
                            "state": "Auto",
                            "district": "Auto",
                            "category": "Auto",
                            "subcategory": "Auto"
                        }
                        
                        try:
                            res = requests.post(INGEST_URL, json=payload, timeout=10)
                            if res.status_code == 200:
                                parsed_res = res.json()
                                ext_count = parsed_res.get("extracted_count", 0)
                                logger.info(f"✅ SUCCESS: Ingested {ext_count} new businesses into the database!")
                            else:
                                logger.error(f"❌ Failed to ingest to backend. Status: {res.status_code}")
                        except Exception as req_err:
                            logger.error(f"❌ Error sending data to backend: {req_err}")
                            
            except json.JSONDecodeError:
                pass # Not JSON, ignore
            except Exception as e:
                logger.error(f"Error processing response: {e}")
