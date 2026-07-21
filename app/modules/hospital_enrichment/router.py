from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db, SessionLocal
from app import models

from . import service

router = APIRouter()

_startup_db = SessionLocal()
try:
    service.reconcile_orphaned_jobs(_startup_db)
finally:
    _startup_db.close()


class StartJobRequest(BaseModel):
    district: Optional[str] = None
    category_keywords: List[str] = []  # defaults to ["hospital"] if empty
    include_partial: bool = False
    max_listings: Optional[int] = None


@router.post("/api/v1/hospital_enrichment/jobs")
def start_job(request: StartJobRequest, db: Session = Depends(get_db)):
    try:
        job_id = service.start_job(
            db,
            district_filter=request.district,
            category_keywords=request.category_keywords,
            include_partial=request.include_partial,
            max_listings=request.max_listings,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"job_id": job_id, "status": "started"}


@router.get("/api/v1/hospital_enrichment/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(models.HospitalEnrichmentJob).filter(models.HospitalEnrichmentJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return service.serialize_job(job, include_log=True)


@router.get("/api/v1/hospital_enrichment/jobs")
def list_jobs(limit: int = 10, db: Session = Depends(get_db)):
    jobs = db.query(models.HospitalEnrichmentJob).order_by(
        models.HospitalEnrichmentJob.created_at.desc()
    ).limit(limit).all()
    return {"jobs": [service.serialize_job(j) for j in jobs]}


@router.post("/api/v1/hospital_enrichment/jobs/{job_id}/pause")
def pause_job(job_id: str, db: Session = Depends(get_db)):
    try:
        return service.set_control(db, job_id, "pause")
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/api/v1/hospital_enrichment/jobs/{job_id}/resume")
def resume_job(job_id: str, db: Session = Depends(get_db)):
    try:
        return service.set_control(db, job_id, "run")
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/api/v1/hospital_enrichment/jobs/{job_id}/stop")
def stop_job(job_id: str, db: Session = Depends(get_db)):
    try:
        return service.set_control(db, job_id, "stop")
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.get("/api/v1/hospital_enrichment/stats")
def get_stats(db: Session = Depends(get_db)):
    return service.get_stats(db)


@router.get("/api/v1/hospital_enrichment/results")
def list_results(status: Optional[str] = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    return service.list_results(db, status=status, limit=limit, offset=offset)


@router.get("/api/v1/hospital_enrichment/listings/{listing_id}")
def get_listing_detail(listing_id: int, db: Session = Depends(get_db)):
    try:
        return service.get_listing_detail(db, listing_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="No enrichment profile for this listing")
