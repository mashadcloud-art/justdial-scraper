"""
Hospital enrichment module business logic: seeding HospitalProfile rows for
hospital-category listings, running the background worker thread, and job
control (pause/resume/stop). The actual crawling lives in engine.py.

Resumability model: progress lives on HospitalProfile.overall_status, not on the
job row. Starting a job seeds any hospital listings that don't have a profile yet
(existing profiles — including ones left "in_progress" by a killed process — are
left alone) and the worker just keeps pulling whatever is still pending/failed
across the whole table. So killing the process and starting a fresh job later
resumes exactly where the last one stopped; nothing is re-done or lost.
"""
import json
import time
import uuid
import threading
from datetime import datetime

from sqlalchemy import or_, func
from playwright.sync_api import sync_playwright

from app.database import SessionLocal
from app import models
from . import engine

MAX_ATTEMPTS = 3
PER_LISTING_DELAY_SECONDS = 1.5  # be polite to hospital sites we're crawling
DEFAULT_CATEGORY_KEYWORDS = ["hospital"]

_job_lock = threading.Lock()
_running_job_ids = set()

# District names are stored inconsistently (mixed case, e.g. both 'Ernakulam'
# and 'ernakulam' exist as distinct values) and some are commonly known by an
# older/alternate name. Match on lowercase and expand to every known variant.
KERALA_DISTRICT_ALIASES = [
    ["thiruvananthapuram", "trivandrum"],
    ["kollam", "quilon"],
    ["pathanamthitta"],
    ["alappuzha", "alleppey"],
    ["kottayam"],
    ["idukki"],
    ["ernakulam", "kochi", "cochin"],
    ["thrissur", "trichur"],
    ["palakkad", "palghat"],
    ["malappuram"],
    ["kozhikode", "calicut"],
    ["wayanad"],
    ["kannur", "cannanore"],
    ["kasaragod", "kasargod"],
]


def _district_variants(district: str) -> list:
    key = district.strip().lower()
    for group in KERALA_DISTRICT_ALIASES:
        if key in group:
            return group
    return [key]


def _log(job: models.HospitalEnrichmentJob, msg: str):
    try:
        lines = json.loads(job.log_tail) if job.log_tail else []
    except Exception:
        lines = []
    lines.append({"time": datetime.now().strftime("%H:%M:%S"), "msg": msg})
    job.log_tail = json.dumps(lines[-200:])
    print(f"[hospital_enrichment] {msg}")


def _hospital_listing_filter(query, category_keywords: list, district: str = None):
    keyword_clauses = []
    for kw in category_keywords:
        like = f"%{kw}%"
        keyword_clauses.append(models.Listing.category.ilike(like))
        keyword_clauses.append(models.Listing.subcategory.ilike(like))
    query = query.filter(or_(*keyword_clauses))
    if district:
        query = query.filter(func.lower(models.Listing.district).in_(_district_variants(district)))
    return query


def _seed_profiles(db, job: models.HospitalEnrichmentJob) -> int:
    """Insert a pending HospitalProfile for every matching listing that doesn't have
    one yet. Idempotent — safe to call again for a fresh job over the same scope."""
    keywords = [k.strip() for k in (job.category_keywords or "").split(",") if k.strip()] or DEFAULT_CATEGORY_KEYWORDS
    query = _hospital_listing_filter(db.query(models.Listing.id), keywords, job.district_filter)
    if job.max_listings:
        query = query.limit(job.max_listings)
    listing_ids = [row[0] for row in query.all()]

    existing_ids = {
        row[0] for row in db.query(models.HospitalProfile.listing_id)
        .filter(models.HospitalProfile.listing_id.in_(listing_ids)).all()
    } if listing_ids else set()

    created = 0
    for listing_id in listing_ids:
        if listing_id in existing_ids:
            continue
        db.add(models.HospitalProfile(listing_id=listing_id, overall_status="pending"))
        created += 1
    db.commit()
    return len(listing_ids)


def _next_pending_profile(db, job: models.HospitalEnrichmentJob):
    """Claims the next profile to work on: never-attempted rows first, then
    previously-failed rows under the retry cap, then (if requested) partial results
    to re-crawl. Marking it in_progress immediately is what makes a crash mid-run
    resumable instead of reprocessed as 'pending' forever or duplicated."""
    statuses = ["pending", "failed"]
    if job.include_partial:
        statuses.append("completed_partial")

    keywords = [k.strip() for k in (job.category_keywords or "").split(",") if k.strip()] or DEFAULT_CATEGORY_KEYWORDS
    scoped_listing_ids = _hospital_listing_filter(db.query(models.Listing.id), keywords, job.district_filter)

    # attempts < MAX_ATTEMPTS applies uniformly, including to completed_partial rows —
    # without this a listing whose partial result is stable (e.g. real site, no doctors
    # page) would be re-picked every single iteration and the worker would never move
    # on to the rest of the run.
    profile = (
        db.query(models.HospitalProfile)
        .filter(models.HospitalProfile.listing_id.in_(scoped_listing_ids))
        .filter(models.HospitalProfile.overall_status.in_(statuses))
        .filter(models.HospitalProfile.attempts < MAX_ATTEMPTS)
        .order_by(models.HospitalProfile.id.asc())
        .first()
    )
    if profile is not None:
        profile.overall_status = "in_progress"
        db.commit()
    return profile


def _apply_result(db, profile: models.HospitalProfile, result: "engine.EnrichmentResult"):
    profile.website_url = result.website_url
    profile.website_status = result.website_status
    profile.website_match_confidence = result.website_match_confidence
    profile.gallery_status = result.gallery_status
    profile.doctors_page_url = result.doctors_page_url
    profile.doctors_page_status = result.doctors_page_status
    profile.overall_status = result.overall_status
    profile.error_detail = result.error_detail
    profile.attempts = (profile.attempts or 0) + 1
    profile.last_attempted_at = datetime.utcnow()
    if result.overall_status in ("completed", "completed_partial"):
        profile.completed_at = datetime.utcnow()

    db.query(models.HospitalGalleryImage).filter(
        models.HospitalGalleryImage.hospital_profile_id == profile.id
    ).delete()
    for idx, url in enumerate(result.gallery_images):
        db.add(models.HospitalGalleryImage(
            listing_id=profile.listing_id, hospital_profile_id=profile.id, image_url=url, position=idx,
        ))
    profile.gallery_image_count = len(result.gallery_images)

    db.query(models.HospitalDoctor).filter(
        models.HospitalDoctor.hospital_profile_id == profile.id
    ).delete()
    for doc in result.doctors:
        db.add(models.HospitalDoctor(
            listing_id=profile.listing_id, hospital_profile_id=profile.id,
            name=doc["name"], photo_url=doc["photo_url"], photo_status=doc["photo_status"],
            specialty=doc["specialty"], qualifications=doc["qualifications"], experience=doc["experience"],
            phone=doc["phone"], email=doc["email"], source_url=doc["source_url"], raw_text=doc["raw_text"],
        ))
    profile.doctor_count = len(result.doctors)

    db.commit()


def _run_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(models.HospitalEnrichmentJob).filter(models.HospitalEnrichmentJob.job_id == job_id).first()
        if job is None:
            return

        job.status = "seeding"
        db.commit()
        try:
            total = _seed_profiles(db, job)
            job.total_listings = total
            _log(job, f"Seeded run scope: {total} hospital listings.")
        except Exception as e:
            job.status = "failed"
            _log(job, f"Seeding failed: {e}")
            db.commit()
            return

        job.status = "running"
        db.commit()

        # One browser tab, reused for every website-search lookup in this run (see
        # engine.search_candidates for why a real browser is needed, not requests).
        # If Playwright can't launch (e.g. browsers not installed on this host), we
        # degrade gracefully: listings without an existing website simply resolve to
        # website_status="not_found" instead of the worker crashing.
        search_page = None
        playwright_ctx = None
        browser = None
        try:
            playwright_ctx = sync_playwright().start()
            browser = playwright_ctx.chromium.launch(headless=True)
            search_page = browser.new_context(user_agent=engine.USER_AGENT).new_page()
        except Exception as e:
            _log(job, f"Could not start browser for website search ({e}) — "
                      f"will only resolve websites already present on listings.")
            db.commit()

        try:
            while True:
                db.refresh(job)
                if job.control == "stop":
                    job.status = "stopped"
                    _log(job, "Stopped by request.")
                    db.commit()
                    break
                if job.control == "pause":
                    if job.status != "paused":
                        job.status = "paused"
                        _log(job, "Paused.")
                        db.commit()
                    time.sleep(2)
                    continue
                if job.status == "paused":
                    job.status = "running"
                    _log(job, "Resumed.")
                    db.commit()

                profile = _next_pending_profile(db, job)
                if profile is None:
                    job.status = "completed"
                    job.completed_at = datetime.utcnow()
                    _log(job, "No more pending hospitals — run complete.")
                    db.commit()
                    break

                listing = db.query(models.Listing).filter(models.Listing.id == profile.listing_id).first()
                if listing is None:
                    # Listing was deleted since seeding — drop the orphaned profile and move on.
                    db.delete(profile)
                    db.commit()
                    continue

                city = listing.district or listing.place or ""
                try:
                    result = engine.enrich_listing(listing.name, city, listing.jd_url, search_page=search_page)
                except Exception as e:
                    profile.overall_status = "failed"
                    profile.error_detail = f"Unexpected error: {e}"
                    profile.attempts = (profile.attempts or 0) + 1
                    profile.last_attempted_at = datetime.utcnow()
                    db.commit()
                    result = None

                if result is not None:
                    _apply_result(db, profile, result)

                job.processed = (job.processed or 0) + 1
                final_status = profile.overall_status
                if final_status == "completed":
                    job.succeeded = (job.succeeded or 0) + 1
                elif final_status == "completed_partial":
                    job.partial = (job.partial or 0) + 1
                else:
                    job.failed = (job.failed or 0) + 1
                _log(job, f"[{job.processed}/{job.total_listings}] {listing.name} -> {final_status} "
                          f"(website={profile.website_status}, gallery={profile.gallery_status}, "
                          f"doctors={profile.doctors_page_status})")
                db.commit()

                time.sleep(PER_LISTING_DELAY_SECONDS)
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright_ctx is not None:
                try:
                    playwright_ctx.stop()
                except Exception:
                    pass
    finally:
        db.close()
        with _job_lock:
            _running_job_ids.discard(job_id)


def reconcile_orphaned_jobs(db):
    """Worker threads are in-memory and die with the backend process. If the
    process was killed/restarted while a job was pending/seeding/running/paused,
    that row is stuck forever — no thread is left to ever act on control="stop"
    or finish it, and it permanently blocks start_job()'s active-job guard.
    Run once at backend startup to close out anything left in that state."""
    stuck = db.query(models.HospitalEnrichmentJob).filter(
        models.HospitalEnrichmentJob.status.in_(["pending", "seeding", "running", "paused"])
    ).all()
    for job in stuck:
        job.status = "stopped"
        job.control = "stop"
        _log(job, "Marked stopped on backend startup (previous worker did not survive a restart).")
    if stuck:
        db.commit()


def start_job(db, district_filter: str = None, category_keywords: list = None,
              include_partial: bool = False, max_listings: int = None) -> str:
    active = db.query(models.HospitalEnrichmentJob).filter(
        models.HospitalEnrichmentJob.status.in_(["pending", "seeding", "running", "paused"])
    ).first()
    if active:
        raise ValueError(f"A hospital enrichment job is already active (job_id={active.job_id})")

    job_id = uuid.uuid4().hex[:12]
    job = models.HospitalEnrichmentJob(
        job_id=job_id,
        status="pending",
        district_filter=district_filter or None,
        category_keywords=",".join(category_keywords) if category_keywords else None,
        include_partial=include_partial,
        max_listings=max_listings,
    )
    db.add(job)
    db.commit()

    with _job_lock:
        _running_job_ids.add(job_id)
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return job_id


def serialize_job(job: models.HospitalEnrichmentJob, include_log: bool = False) -> dict:
    data = {
        "job_id": job.job_id,
        "status": job.status,
        "control": job.control or "run",
        "district_filter": job.district_filter,
        "category_keywords": job.category_keywords,
        "include_partial": job.include_partial,
        "max_listings": job.max_listings,
        "total_listings": job.total_listings,
        "processed": job.processed,
        "succeeded": job.succeeded,
        "partial": job.partial,
        "failed": job.failed,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "completed_at": job.completed_at,
    }
    if include_log:
        try:
            data["log_tail"] = json.loads(job.log_tail) if job.log_tail else []
        except Exception:
            data["log_tail"] = []
    return data


def set_control(db, job_id: str, control: str) -> dict:
    job = db.query(models.HospitalEnrichmentJob).filter(models.HospitalEnrichmentJob.job_id == job_id).first()
    if job is None:
        raise KeyError(job_id)
    job.control = control
    if control == "stop" and job.status in ("pending", "seeding"):
        job.status = "stopped"
    db.commit()
    return serialize_job(job)


def serialize_profile(profile: models.HospitalProfile, listing: models.Listing = None) -> dict:
    return {
        "listing_id": profile.listing_id,
        "listing_name": listing.name if listing else None,
        "listing_district": listing.district if listing else None,
        "website_url": profile.website_url,
        "website_status": profile.website_status,
        "website_match_confidence": profile.website_match_confidence,
        "gallery_status": profile.gallery_status,
        "gallery_image_count": profile.gallery_image_count,
        "doctors_page_url": profile.doctors_page_url,
        "doctors_page_status": profile.doctors_page_status,
        "doctor_count": profile.doctor_count,
        "overall_status": profile.overall_status,
        "error_detail": profile.error_detail,
        "attempts": profile.attempts,
        "last_attempted_at": profile.last_attempted_at,
        "completed_at": profile.completed_at,
    }


def serialize_doctor(doc: models.HospitalDoctor) -> dict:
    return {
        "id": doc.id,
        "name": doc.name,
        "photo_url": doc.photo_url,
        "photo_status": doc.photo_status,
        "specialty": doc.specialty,
        "qualifications": doc.qualifications,
        "experience": doc.experience,
        "phone": doc.phone,
        "email": doc.email,
        "source_url": doc.source_url,
    }


def get_listing_detail(db, listing_id: int) -> dict:
    profile = db.query(models.HospitalProfile).filter(models.HospitalProfile.listing_id == listing_id).first()
    if profile is None:
        raise KeyError(listing_id)
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    images = db.query(models.HospitalGalleryImage).filter(
        models.HospitalGalleryImage.hospital_profile_id == profile.id
    ).order_by(models.HospitalGalleryImage.position).all()
    doctors = db.query(models.HospitalDoctor).filter(
        models.HospitalDoctor.hospital_profile_id == profile.id
    ).order_by(models.HospitalDoctor.id).all()

    data = serialize_profile(profile, listing)
    data["gallery_images"] = [img.image_url for img in images]
    data["doctors"] = [serialize_doctor(d) for d in doctors]
    return data


def list_results(db, status: str = None, limit: int = 50, offset: int = 0) -> dict:
    query = db.query(models.HospitalProfile, models.Listing).join(
        models.Listing, models.Listing.id == models.HospitalProfile.listing_id
    )
    if status:
        query = query.filter(models.HospitalProfile.overall_status == status)
    total = query.count()
    rows = query.order_by(models.HospitalProfile.updated_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "results": [serialize_profile(profile, listing) for profile, listing in rows],
    }


def get_stats(db) -> dict:
    rows = db.query(models.HospitalProfile.overall_status, models.HospitalProfile.id).all()
    by_status = {}
    for status, _ in rows:
        by_status[status] = by_status.get(status, 0) + 1
    doctor_total = db.query(models.HospitalDoctor.id).count()
    doctor_with_photo = db.query(models.HospitalDoctor.id).filter(models.HospitalDoctor.photo_status == "found").count()
    gallery_image_total = db.query(models.HospitalGalleryImage.id).count()
    return {
        "total_profiles": len(rows),
        "by_overall_status": by_status,
        "total_doctors": doctor_total,
        "doctors_with_photo": doctor_with_photo,
        "total_gallery_images": gallery_image_total,
    }
