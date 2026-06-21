import json
import logging
import os
import time
from mitmproxy import http

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - MITM-SAVER - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directory where we will save the raw JSONs
SAVE_DIR = r"c:\Users\PC\Desktop\JustDial_JSONs"
os.makedirs(SAVE_DIR, exist_ok=True)

def response(flow: http.HTTPFlow):
    """
    Intercepts JustDial API responses and saves them directly to a local folder.
    Does NOT upload to the database automatically.
    """
    if "justdial.com" in flow.request.url and flow.response:
        content_type = flow.response.headers.get("Content-Type", "")
        if "application/json" in content_type or "text/json" in content_type or "application/javascript" in content_type:
            try:
                body = flow.response.get_text()
                if not body:
                    return
                
                data = json.loads(body)
                
                # Check if it has the results structure
                if "results" in data and isinstance(data["results"], dict) and "data" in data["results"]:
                    rows = data["results"]["data"]
                    if len(rows) > 0:
                        timestamp = int(time.time())
                        filename = f"justdial_listings_{timestamp}.json"
                        file_path = os.path.join(SAVE_DIR, filename)
                        
                        # Save the raw JSON data
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(body)
                            
                        logger.info(f"💾 SAVED! {len(rows)} listings saved to: {file_path}")
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.error(f"Error saving response: {e}")
