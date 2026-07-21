import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter()

_status = {"active": False, "done": True, "found": 0, "saved": 0, "round": 0}


class DiscoverRequest(BaseModel):
    district: str
    category: str


def _run(district: str, category: str):
    try:
        service.discover(district, category, status=_status)
    except Exception as e:
        _status["error"] = str(e)
        _status["done"] = True
    finally:
        _status["active"] = False


@router.post("/api/v1/jd_discovery/start")
def start_discovery(request: DiscoverRequest):
    if _status.get("active"):
        raise HTTPException(status_code=400, detail="A discovery run is already active")
    if not request.district.strip() or not request.category.strip():
        raise HTTPException(status_code=400, detail="district and category are required")

    _status.clear()
    _status.update({
        "active": True, "done": False, "found": 0, "saved": 0, "round": 0,
        "district": request.district, "category": request.category,
    })
    threading.Thread(target=_run, args=(request.district, request.category), daemon=True).start()
    return {"status": "started"}


@router.get("/api/v1/jd_discovery/status")
def get_status():
    return _status
