from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter()


class StartScrapeRequest(BaseModel):
    district: str = ""
    category: str = ""
    max_results: int = 100
    auto_sync: bool = True


class SyncRequest(BaseModel):
    district: str = ""
    category: str = ""
    limit: int = 1


@router.post("/api/v1/map_scraper/start")
def start_map_scrape(request: StartScrapeRequest):
    if not (1 <= request.max_results <= 500):
        raise HTTPException(status_code=400, detail="max_results must be between 1 and 500")

    result = service.start_scrape(
        request.district, request.category, request.max_results, request.auto_sync
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to start scrape"))
    return {"status": "started", "query": result["query"], "district": request.district,
            "category": request.category, "auto_sync": request.auto_sync}


@router.get("/api/v1/map_scraper/status")
def map_scrape_status():
    return service.get_status()


@router.get("/api/v1/map_scraper/results")
def map_scrape_results(limit: int = 1):
    result = service.get_results(limit=limit)
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Failed to fetch results from thozil"))
    return result


@router.get("/api/v1/map_scraper/log")
def map_scrape_log(last_idx: int = 0):
    return service.get_log(last_idx)


@router.post("/api/v1/map_scraper/sync")
def sync_map_scrape(request: SyncRequest):
    result = service.sync_latest(request.district, request.category, request.limit)
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Failed to sync results"))
    return result
