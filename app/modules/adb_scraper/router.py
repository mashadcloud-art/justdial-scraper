from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter()


class StartRequest(BaseModel):
    district: str
    category: str
    scrolls: int = 10


@router.post("/api/v1/adb_scraper/start")
def start(request: StartRequest):
    try:
        service.start_job(request.district, request.category, request.scrolls)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "started"}


@router.post("/api/v1/adb_scraper/stop")
def stop():
    service.request_stop()
    return {"status": "stopped", "message": "ADB stop signal sent."}


@router.get("/api/v1/adb_scraper/status")
def status(last_idx: int = 0):
    return service.get_status(last_idx)


@router.post("/api/v1/adb_scraper/sync")
def sync(district: str = "Unknown"):
    """Push everything captured locally by the MITM addon into Supabase."""
    return service.sync_to_db(district)
