"""
Dashboard module business logic: user scoping and background-daemon process
detection, kept independent of the scraper module's own copy.
"""
import json
from typing import Optional

import psutil


def get_current_user(authorization: Optional[str]) -> Optional[dict]:
    """Decode the (unverified) JWT bearer token to scope requests by user_id."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    if not token or token == "null" or token == "undefined":
        return None
    try:
        import base64
        payload_segment = token.split(".")[1]
        padded = payload_segment + "=" * (4 - len(payload_segment) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(decoded_bytes.decode("utf-8"))
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email")
        }
    except Exception:
        return None


def is_background_daemon_running() -> bool:
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            if any('scrape_background_images.py' in part for part in cmd):
                return True
        except Exception:
            pass
    return False
