"""
Deep-scrape module business logic: job creation/serialization.
The actual scraping engine lives in app/scraper/deep_category_scraper.py
(untouched — also imported directly by app/api/categories.py-adjacent code).
"""
import json
import uuid
import threading

from app import models
from app.scraper.deep_category_scraper import run_deep_scrape_job


def start_job(db, url: str, mode: str, manual_subcategories: list) -> str:
    job_id = uuid.uuid4().hex[:12]
    job = models.DeepScrapeJob(
        job_id=job_id,
        url=url,
        mode=mode,
        status="pending",
    )
    db.add(job)
    db.commit()

    threading.Thread(
        target=run_deep_scrape_job,
        args=(job_id, url, mode),
        kwargs={"manual_subcategories": manual_subcategories},
        daemon=True
    ).start()

    return job_id


def serialize_job(job, include_log: bool = False) -> dict:
    data = {
        "job_id": job.job_id,
        "url": job.url,
        "mode": job.mode,
        "status": job.status,
        "control": job.control or "run",
        "total_subcategories": job.total_subcategories,
        "completed_subcategories": job.completed_subcategories,
        "total_found": job.total_found,
        "duplicates_skipped": job.duplicates_skipped,
        "saved_to_db": (job.total_found or 0) - (job.duplicates_skipped or 0),
        "current_subcategory": job.current_subcategory,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if include_log:
        try:
            data["log_tail"] = json.loads(job.log_tail) if job.log_tail else []
        except Exception:
            data["log_tail"] = []
    return data


def delete_job(db, job_id: str) -> dict:
    job = db.query(models.DeepScrapeJob).filter(models.DeepScrapeJob.job_id == job_id).first()
    if job is None:
        raise KeyError(job_id)
    if job.status in ("pending", "discovering", "scraping") and job.control != "stop":
        raise ValueError("Stop the job before deleting it")
    db.delete(job)
    db.commit()
    return {"status": "deleted", "job_id": job_id}


def set_control(db, job_id: str, control: str) -> dict:
    """Signal the running worker thread to pause/resume/stop at its next per-subcategory checkpoint."""
    job = db.query(models.DeepScrapeJob).filter(models.DeepScrapeJob.job_id == job_id).first()
    if job is None:
        raise KeyError(job_id)
    job.control = control
    if control == "stop" and job.status in ("pending", "discovering"):
        # Nothing is between subcategories yet to catch the flag — stop immediately.
        job.status = "stopped"
    db.commit()
    return serialize_job(job)
