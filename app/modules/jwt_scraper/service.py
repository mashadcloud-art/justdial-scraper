"""
Desktop jwt_api scraper — fully independent of the ADB/mobile path: own in-process
'running' flag, own stop-flag file, own log stream (app.scraper.jwt_logger). Never
touches service.scraping_in_progress or app.scraper.logger — those belong to the
generic /api/v1/scrape engines (api/playwright/selenium) and, previously, emulator.
"""
import os
import threading

from config import settings
from app.scraper.jwt_logger import scraper_logger, log

STOP_FLAG_PATH = os.path.join(settings.DATA_FOLDER, "jwt_scrape_stop.flag")

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


def _run(state: str, district: str, category: str, pages: int, force: bool):
    global running
    try:
        from jd_api_scraper import scrape_jwt_city
        from app.scraper.deep_category_scraper import resolve_category
        from app.database import SessionLocal
        from app.scraper.constants import CITIES

        target_state = state or "Kerala"
        districts_to_scrape = []
        if district.lower() == "all":
            districts_to_scrape = [d for d in CITIES.get(target_state, []) if d.lower() != "all"]
        else:
            districts_to_scrape = [district]

        total_inserted = 0
        total_seen = 0

        for current_dist in districts_to_scrape:
            # Check for stop flag between districts
            if os.path.exists(STOP_FLAG_PATH):
                log("Stop requested by user. Aborting remaining districts.")
                break

            log(f"\n--- Starting Scrape District: {current_dist} ---")
            db = SessionLocal()
            try:
                resolved, ncatid = resolve_category(db, current_dist, category)
            except Exception:
                resolved, ncatid = category, None
            finally:
                db.close()

            log(f"Resolved category '{category}' -> '{resolved}' (ncatid={ncatid}) for {current_dist}")
            inserted, seen = scrape_jwt_city(current_dist, resolved, pages=pages, limit=100, dry_run=False, force=force, ncatid=ncatid)
            total_inserted += inserted
            total_seen += seen

            if inserted + seen == 0:
                log(f"'{resolved}' in {current_dist} returned 0 results from the API.", ok=False)
            else:
                log(f"Finished {current_dist}. Inserted {inserted}, saw {seen} rows.")

        log(f"\n=== ALL DISTRICTS SCRAPE RUN COMPLETED ===")
        log(f"Total Inserted: {total_inserted}, Total Seen: {total_seen}")
    except Exception as e:
        log(f"Scrape failed: {e}", ok=False)
    finally:
        running = False


def start_job(district: str, category: str, pages: int = 999999, force: bool = False, state: str = "Kerala"):
    global running
    if running:
        raise ValueError("A jwt_api scrape is already running")
    clear_stop_flag()
    scraper_logger.clear()
    running = True
    log(f"Starting jwt_api scrape: '{category}' in {district} ({state}) (force={force})")
    threading.Thread(target=_run, args=(state, district, category, pages, force), daemon=True).start()


def get_status(last_idx: int = 0):
    logs, next_idx = scraper_logger.get_logs(last_idx)
    return {"running": running, "logs": logs, "next_idx": next_idx}
