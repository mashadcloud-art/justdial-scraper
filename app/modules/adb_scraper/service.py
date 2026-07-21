"""
ADB/emulator UI-automation scraper — fully independent of the jwt_api desktop path:
own in-process 'running' flag, own stop-flag file, own log stream
(app.scraper.adb_logger). Results are captured by the MITM proxy addon straight to
a local JSON folder (see app/scraper/mitm_saver.py) — never written to the live DB
directly. sync_to_db() is the explicit, separate step that pushes that local data in.
"""
import os
import threading

from config import settings
from app.scraper.adb_logger import scraper_logger, log

STOP_FLAG_PATH = os.path.join(settings.DATA_FOLDER, "adb_scrape_stop.flag")
MITM_SAVE_DIR = r"c:\Users\PC\Desktop\JustDial_JSONs"  # matches app/scraper/mitm_saver.py SAVE_DIR

running = False


def clear_stop_flag():
    if os.path.exists(STOP_FLAG_PATH):
        try:
            os.remove(STOP_FLAG_PATH)
        except Exception:
            pass


def request_stop():
    os.makedirs(os.path.dirname(STOP_FLAG_PATH), exist_ok=True)
    with open(STOP_FLAG_PATH, "w") as f:
        f.write("stop")
    log("Stop requested by user.")


def _run(district: str, category: str, scrolls: int):
    global running
    try:
        from app.scraper.adb_location_search import automate_location_search
        from app.scraper.constants import get_areas_for_district

        areas = get_areas_for_district(district) or [district]
        log(f"ADB scrape: '{category}' in '{district}' — {len(areas)} areas: {', '.join(areas)}")
        automate_location_search(areas, category, scrolls=scrolls, city=district)
        log("ADB scrape finished.")
    except Exception as e:
        log(f"ADB scrape failed: {e}", ok=False)
    finally:
        running = False


def start_job(district: str, category: str, scrolls: int = 10):
    global running
    if running:
        raise ValueError("An ADB scrape is already running")
    clear_stop_flag()
    scraper_logger.clear()
    running = True
    threading.Thread(target=_run, args=(district, category, scrolls), daemon=True).start()


def get_status(last_idx: int = 0):
    logs, next_idx = scraper_logger.get_logs(last_idx)
    return {"running": running, "logs": logs, "next_idx": next_idx}


def sync_to_db(district: str = "Unknown"):
    """Explicit step: push everything the MITM addon has captured locally into Supabase."""
    from app.modules.scraper.router import ingest_saved_folder
    return ingest_saved_folder(district=district, folder_path=MITM_SAVE_DIR)
