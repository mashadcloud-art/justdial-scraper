from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter()


class StartScrapeRequest(BaseModel):
    district: str
    category: str
    pages: int = 10
    subcategories: bool = True


@router.post("/api/v1/mobile_scraper/start")
def start_mobile_scrape(request: StartScrapeRequest):
    if not request.category:
        raise HTTPException(status_code=400, detail="category is required")
    if not (1 <= request.pages <= 50):
        raise HTTPException(status_code=400, detail="pages must be between 1 and 50")

    result = service.start_scrape(
        request.district, request.category, request.pages, request.subcategories
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to start scrape"))
    return {"status": "started", "district": request.district, "category": request.category,
            "pages": request.pages, "subcategories": request.subcategories}


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
