"""
Google Maps ADB scraper API endpoints.
Completely separate from existing scraper endpoints.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional
import threading

from app.scraper.logger import scraper_logger, log

router = APIRouter(prefix="/api/v1/gmaps", tags=["gmaps"])

gmaps_in_progress = False


class GMapsRequest(BaseModel):
    query: str                    # e.g. "Hospitals in Abu Dhabi"
    max_results: int = 20
    scroll_count: int = 5
    district: str = ""
    upload_to_db: bool = True


@router.post("/scrape")
def trigger_gmaps_scrape(request: GMapsRequest,
                          background_tasks: BackgroundTasks = None):
    """Start a Google Maps ADB scrape for a given query."""
    global gmaps_in_progress
    if gmaps_in_progress:
        raise HTTPException(status_code=400,
                            detail="Google Maps scrape already in progress.")

    scraper_logger.clear()

    def run():
        global gmaps_in_progress
        gmaps_in_progress = True
        try:
            from app.scraper.gmaps_scraper import scrape_gmaps, save_results, upload_to_db
            log(f"🗺️ Starting Google Maps scrape: {request.query}")
            results = scrape_gmaps(
                query=request.query,
                max_results=request.max_results,
                scroll_count=request.scroll_count
            )
            save_results(results)
            if request.upload_to_db:
                count = upload_to_db(results, district=request.district)
                log(f"✅ Uploaded {count} results to database.")
            else:
                log(f"✅ Scrape complete. {len(results['results'])} results (not uploaded).")
        except Exception as e:
            log(f"❌ Google Maps scrape failed: {e}", ok=False)
        finally:
            gmaps_in_progress = False
            log("🏁 Google Maps scrape task completed.")

    if background_tasks:
        background_tasks.add_task(run)
    else:
        threading.Thread(target=run, daemon=True).start()

    return {"status": "started",
            "message": f"Google Maps scrape started for: {request.query}"}


@router.get("/status")
def get_gmaps_status(last_idx: int = 0):
    """Get current scrape status and logs."""
    global gmaps_in_progress
    new_logs, next_idx = scraper_logger.get_logs(last_idx)
    return {
        "running": gmaps_in_progress,
        "logs": new_logs,
        "next_idx": next_idx
    }


@router.post("/reset")
def reset_gmaps_lock():
    """Force-reset the scrape lock if stuck."""
    global gmaps_in_progress
    was_locked = gmaps_in_progress
    gmaps_in_progress = False
    return {"status": "reset", "was_locked": was_locked}


@router.get("/generate-intent")
def generate_intent(query: str):
    """
    Generate the ADB intent + extraction pipeline for a given query.
    Useful for debugging or manual execution.
    """
    encoded = query.replace(" ", "+")
    return {
        "query": query,
        "adb_intent": (
            f'adb shell am start -a android.intent.action.VIEW '
            f'-d "geo:0,0?q={encoded}" '
            f'-n com.google.android.apps.maps/com.google.android.maps.MapsActivity'
        ),
        "list_extraction": [
            "Wait 4 seconds for Maps to load",
            "adb shell uiautomator dump /sdcard/gmaps_list.xml",
            "adb pull /sdcard/gmaps_list.xml",
            "Parse clickable nodes for business names + tap coordinates",
            "Scroll: adb shell input swipe 540 1200 540 400 800",
            "Repeat until enough results collected"
        ],
        "detail_extraction": [
            "For each list item:",
            "  adb shell input tap <x> <y>   # open detail page",
            "  Wait 3 seconds",
            "  adb shell uiautomator dump /sdcard/gmaps_detail.xml",
            "  adb pull /sdcard/gmaps_detail.xml",
            "  Parse: name, address, phone, website, rating, reviews, hours",
            "  adb shell dumpsys activity | grep geo:   # get coordinates",
            "  adb shell input keyevent 4               # go back"
        ],
        "expected_json": {
            "query": query,
            "results": [
                {
                    "name": "",
                    "address": "",
                    "phone": "",
                    "website": "",
                    "rating": "",
                    "reviews": "",
                    "hours": "",
                    "category": "",
                    "latitude": "",
                    "longitude": ""
                }
            ]
        }
    }
