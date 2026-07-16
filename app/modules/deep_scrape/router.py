from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.scraper.deep_category_scraper import ensure_seed_category_map, parse_category_url, save_html_subcategories_to_map

from . import service

router = APIRouter()


class DeepScrapeRequest(BaseModel):
    url: str
    mode: str  # "district" or "state"
    manual_subcategories: list = []  # optional override list


@router.post("/api/v1/deep-scrape")
def start_deep_scrape(request: DeepScrapeRequest, db: Session = Depends(get_db)):
    if request.mode not in ("district", "state"):
        raise HTTPException(status_code=400, detail="mode must be 'district' or 'state'")

    # For manual category scrapes, URL doesn't need to be a real JustDial URL
    if not request.url:
        raise HTTPException(status_code=400, detail="A category URL is required")

    active_job = db.query(models.DeepScrapeJob).filter(
        models.DeepScrapeJob.status.in_(["pending", "discovering", "scraping"])
    ).first()
    if active_job:
        raise HTTPException(status_code=400, detail=f"A deep-scrape job is already running (job_id={active_job.job_id})")

    job_id = service.start_job(db, request.url, request.mode, request.manual_subcategories)
    return {"job_id": job_id, "status": "started"}


@router.get("/api/v1/deep-scrape/status/{job_id}")
def get_deep_scrape_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(models.DeepScrapeJob).filter(models.DeepScrapeJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return service.serialize_job(job, include_log=True)


@router.get("/api/v1/deep-scrape/status")
def get_latest_deep_scrape_status(db: Session = Depends(get_db)):
    """Most recent deep-scrape job (running or finished) — lets the frontend reconnect after a refresh."""
    job = db.query(models.DeepScrapeJob).order_by(models.DeepScrapeJob.created_at.desc()).first()
    if not job:
        return {"job": None}
    return {"job": service.serialize_job(job, include_log=True)}


@router.post("/api/v1/deep-scrape/{job_id}/pause")
def pause_deep_scrape(job_id: str, db: Session = Depends(get_db)):
    try:
        return service.set_control(db, job_id, "pause")
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/api/v1/deep-scrape/{job_id}/resume")
def resume_deep_scrape(job_id: str, db: Session = Depends(get_db)):
    try:
        return service.set_control(db, job_id, "run")
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/api/v1/deep-scrape/{job_id}/stop")
def stop_deep_scrape(job_id: str, db: Session = Depends(get_db)):
    try:
        return service.set_control(db, job_id, "stop")
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.delete("/api/v1/deep-scrape/{job_id}")
def delete_deep_scrape_job(job_id: str, db: Session = Depends(get_db)):
    try:
        return service.delete_job(db, job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/v1/deep-scrape/recent")
def get_recent_deep_scrape_jobs(limit: int = 5, db: Session = Depends(get_db)):
    """Last N deep-scrape jobs (any status), newest first, for the Recent Jobs list."""
    jobs = db.query(models.DeepScrapeJob).order_by(models.DeepScrapeJob.created_at.desc()).limit(limit).all()
    return {"jobs": [service.serialize_job(j) for j in jobs]}


class ParseHtmlToCategoryMapRequest(BaseModel):
    url: str
    html_content: str


@router.get("/api/v1/category-map")
def get_category_map(db: Session = Depends(get_db)):
    """Return the current jd_category_map contents, grouped by main category (seeding defaults first)."""
    ensure_seed_category_map(db)

    rows = db.query(models.JDCategoryMap).order_by(
        models.JDCategoryMap.main_category, models.JDCategoryMap.subcategory
    ).all()
    grouped: dict = {}
    for r in rows:
        grouped.setdefault(r.main_category, []).append({
            "subcategory": r.subcategory,
            "tags": r.tags,
            "city": r.city,
        })
    return {"categories": grouped}


@router.post("/api/v1/category-map/parse-html")
def parse_html_to_category_map(request: ParseHtmlToCategoryMapRequest, db: Session = Depends(get_db)):
    """Parse a pasted JustDial category page and save its subcategories (+ tags) into jd_category_map."""
    if not request.html_content or not request.html_content.strip():
        raise HTTPException(status_code=400, detail="HTML content is required")
    try:
        city, category_name = parse_category_url(request.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    saved = save_html_subcategories_to_map(db, category_name, request.html_content, city=city)
    if not saved:
        raise HTTPException(status_code=400, detail="No subcategories found in the pasted HTML")
    return {"main_category": category_name, "city": city, "saved": saved, "count": len(saved)}
