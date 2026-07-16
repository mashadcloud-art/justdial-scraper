"""
Module Store: list every feature module (app/modules/<name>/manifest.json)
along with its enabled/installed state, and let the UI enable/disable or
install/uninstall a module. This is the sole source of truth the frontend
sidebar polls to decide which nav tabs to show.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from . import service

router = APIRouter(prefix="/api/v1/modules", tags=["modules"])


class SetEnabledRequest(BaseModel):
    enabled: bool


@router.get("")
def get_modules(db: Session = Depends(get_db)):
    return service.list_modules(db)


@router.patch("/{module_id}")
def patch_module(module_id: str, body: SetEnabledRequest, db: Session = Depends(get_db)):
    try:
        return service.set_enabled(db, module_id, body.enabled)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown module '{module_id}'.")
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{module_id}/uninstall")
def uninstall_module(module_id: str, db: Session = Depends(get_db)):
    try:
        return service.set_installed(db, module_id, False)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown module '{module_id}'.")
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{module_id}/install")
def install_module(module_id: str, db: Session = Depends(get_db)):
    try:
        return service.set_installed(db, module_id, True)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown module '{module_id}'.")
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))
