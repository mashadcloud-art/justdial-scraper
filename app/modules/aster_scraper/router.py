from fastapi import APIRouter
from pydantic import BaseModel

from . import service

router = APIRouter()


class RunRequest(BaseModel):
    force: bool = False


@router.post("/api/v1/aster_scraper/run")
def run(request: RunRequest):
    return service.start_run(force=request.force)


@router.get("/api/v1/aster_scraper/status")
def status():
    return service.get_status()


@router.get("/api/v1/aster_scraper/report")
def report():
    return service.get_report()
