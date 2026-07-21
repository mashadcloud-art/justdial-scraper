from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter()


class StartRequest(BaseModel):
    district: str
    category: str
    pages: int = 999999
    force: bool = False
    state: str = "Kerala"


@router.post("/api/v1/jwt_scraper/start")
def start(request: StartRequest):
    try:
        service.start_job(request.district, request.category, request.pages, request.force, request.state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "started"}


@router.post("/api/v1/jwt_scraper/stop")
def stop():
    service.request_stop()
    return {"status": "stopped", "message": "jwt_api stop signal sent."}


@router.get("/api/v1/jwt_scraper/status")
def status(last_idx: int = 0):
    return service.get_status(last_idx)
