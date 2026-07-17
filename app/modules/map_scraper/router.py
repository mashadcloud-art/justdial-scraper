from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from . import service

router = APIRouter()


def _check_filename(filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")


class StartScrapeRequest(BaseModel):
    district: str = ""
    category: str = ""
    max_results: int = 100
    auto_sync: bool = True


class CreateScraperRequest(BaseModel):
    id: Optional[str] = None
    name: str
    type: str = "google-maps"  # "google-maps" | "custom"
    query: Optional[str] = None
    max_results: int = 100
    url: Optional[str] = None
    list_selector: Optional[str] = None
    schedule: Optional[str] = None


class RunScraperRequest(BaseModel):
    district: str = ""
    category: str = ""
    auto_sync: bool = True


class SyncRequest(BaseModel):
    filename: Optional[str] = None
    district: str = ""
    category: str = ""


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


@router.get("/api/v1/map_scraper/log")
def map_scrape_log(last_idx: int = 0):
    return service.get_log(last_idx)


@router.get("/api/v1/map_scraper/scrapers")
def list_scrapers():
    result = service.list_scrapers()
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Failed to reach thozil server"))
    return result


@router.post("/api/v1/map_scraper/scrapers")
def create_scraper(request: CreateScraperRequest):
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="name is required")

    if request.type == "google-maps":
        if not request.query:
            raise HTTPException(status_code=400, detail="query is required for a google-maps scraper")
        config = {"query": request.query, "maxResults": request.max_results}
    elif request.type == "custom":
        if not request.url:
            raise HTTPException(status_code=400, detail="url is required for a custom scraper")
        config = {"url": request.url, "listSelector": request.list_selector}
    else:
        raise HTTPException(status_code=400, detail="type must be 'google-maps' or 'custom'")

    result = service.create_scraper(request.id, request.name, request.type, config, request.schedule)
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Failed to create scraper"))
    return result


@router.delete("/api/v1/map_scraper/scrapers/{scraper_id}")
def delete_scraper(scraper_id: str):
    result = service.delete_scraper(scraper_id)
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Failed to delete scraper"))
    return result


@router.post("/api/v1/map_scraper/scrapers/{scraper_id}/run")
def run_scraper(scraper_id: str, request: RunScraperRequest):
    result = service.run_scraper(scraper_id, request.auto_sync, request.district, request.category)
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Failed to run scraper"))
    return result


@router.get("/api/v1/map_scraper/results")
def list_results():
    result = service.list_results()
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Failed to fetch results from thozil"))
    return result


@router.get("/api/v1/map_scraper/results/{filename}")
def get_result(filename: str):
    _check_filename(filename)
    try:
        return service.get_result(filename)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/api/v1/map_scraper/results/{filename}/download")
def download_result(filename: str):
    _check_filename(filename)
    try:
        content, content_type = service.download_result(filename)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=str(e))
    return Response(content=content, media_type=content_type,
                     headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/api/v1/map_scraper/results/{filename}/csv")
def download_result_csv(filename: str):
    _check_filename(filename)
    try:
        text = service.get_result_csv(filename)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=str(e))
    csv_name = filename.replace(".json", ".csv")
    return Response(content=text, media_type="text/csv",
                     headers={"Content-Disposition": f'attachment; filename="{csv_name}"'})


@router.post("/api/v1/map_scraper/sync")
def sync_map_scrape(request: SyncRequest):
    result = service.sync_result(request.filename, request.district, request.category)
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Failed to sync results"))
    return result
