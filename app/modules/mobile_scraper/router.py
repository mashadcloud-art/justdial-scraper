from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter()


class StartScrapeRequest(BaseModel):
    district: str
    category: str
    pages: int = 10


@router.post("/api/v1/mobile_scraper/start")
def start_mobile_scrape(request: StartScrapeRequest):
    if not request.district or not request.category:
        raise HTTPException(status_code=400, detail="district and category are required")
    if not (1 <= request.pages <= 20):
        raise HTTPException(status_code=400, detail="pages must be between 1 and 20")

    result = service.start_scrape(request.district, request.category, request.pages)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to start scrape"))
    return {"status": "started", "district": request.district, "category": request.category, "pages": request.pages}


@router.post("/api/v1/mobile_scraper/stop")
def stop_mobile_scrape():
    result = service.stop_scrape()
    return {"status": "stopped" if result.get("stopped") else "not_running"}


@router.get("/api/v1/mobile_scraper/status")
def mobile_scrape_status():
    return service.get_status()


@router.get("/api/v1/mobile_scraper/log")
def mobile_scrape_log():
    result = service.get_log(50)
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Failed to read log from device"))
    return result
