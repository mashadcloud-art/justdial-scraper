"""
Aster scraper orchestration: the fixed 18-hospital list, DB upserts, pacing, and a
simple in-memory run state (mirrors app/modules/map_scraper/service.py's pattern —
no dedicated job table needed since this is a bounded, resumable-by-DB-state run
rather than an open-ended crawl).

Resumable: re-running skips any hospital whose AsterHospital.status is already
'scraped' (detail) / doctors_status is already 'scraped' (doctor listing), unless
force=True.
"""
import re
import time
import threading
from datetime import datetime

from app.database import SessionLocal
from app import models
from . import engine

# The 18 hospitals as given: "slug-id" -> (doctors_listing_slug, numeric_id)
HOSPITAL_SLUG_IDS = [
    "aster-aadhar-kolhapur-162", "aster-cmi-bangalore-2146", "aster-g-madegowda-hospital-6683",
    "aster-medcity-kochi-2688", "aster-mims-calicut-1678", "aster-mims-kannur-1300",
    "aster-mims-kottakkal-50", "aster-mother-areekode-5502", "aster-narayanadri-tirupati-6083",
    "aster-pmf-kollam-7375", "aster-prime-hyderabad-49", "aster-ramesh-guntur-1965",
    "aster-ramesh-ongole-1968", "aster-ramesh-vijayawada-main-1966", "aster-ramesh-vijayawada-mg-road-1967",
    "aster-rv-bangalore-2077", "aster-whitefield-bangalore-5207", "aster-women-children-bangalore-1640",
]

REQUEST_DELAY_SECONDS = 1.5

_lock = threading.Lock()
_state = {"running": False, "processed": 0, "total": len(HOSPITAL_SLUG_IDS), "started_at": None, "finished_at": None}
_logs: list = []


def _log(msg: str, ok: bool = True):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": msg, "ok": ok}
    with _lock:
        _logs.append(entry)
        if len(_logs) > 500:
            del _logs[:-500]
    print(f"[aster_scraper] {msg}")


def get_log(last_idx: int = 0) -> dict:
    with _lock:
        new = _logs[last_idx:]
        return {"logs": new, "next_idx": len(_logs)}


def get_status() -> dict:
    with _lock:
        return dict(_state)


def _split_slug_id(slug_id: str):
    m = re.match(r"^(.+)-(\d+)$", slug_id)
    if not m:
        raise ValueError(f"Malformed slug-id: {slug_id}")
    return m.group(1), int(m.group(2))


def _upsert_hospital(db, aster_id: int, doctors_slug: str, data: dict) -> models.AsterHospital:
    row = db.query(models.AsterHospital).filter(models.AsterHospital.aster_id == aster_id).first()
    if row is None:
        row = models.AsterHospital(aster_id=aster_id, slug=doctors_slug)
        db.add(row)

    if data.get("ok"):
        for field in ("detail_slug", "name", "address", "phone", "helpline", "email",
                      "specialities", "facilities", "about", "latitude", "longitude",
                      "map_link", "source_url"):
            setattr(row, field, data.get(field))
        row.status = "scraped"
        row.error_detail = None
        row.scraped_at = datetime.utcnow()
    else:
        row.status = "failed"
        row.error_detail = data.get("error")
    db.commit()
    return row


def _save_doctors_page(db, hospital_row: models.AsterHospital, doctors: list) -> int:
    """Insert new doctors, skipping any whose detail_url already exists (dedup)."""
    existing_urls = {
        u for (u,) in db.query(models.AsterDoctor.detail_url)
        .filter(models.AsterDoctor.detail_url.in_([d["detail_url"] for d in doctors])).all()
    }
    added = 0
    for d in doctors:
        if d["detail_url"] in existing_urls:
            continue
        db.add(models.AsterDoctor(
            hospital_aster_id=hospital_row.aster_id,
            name=d["name"], detail_url=d["detail_url"], designation=d["designation"],
            qualifications=d["qualifications"], speciality=d["speciality"],
            hospital_name_raw=d["hospital_name_raw"], bio_snippet=d["bio_snippet"],
        ))
        added += 1
    db.commit()
    return added


def _run(force: bool):
    db = SessionLocal()
    with _lock:
        _state.update(running=True, processed=0, started_at=datetime.utcnow().isoformat(), finished_at=None)
    try:
        for slug_id in HOSPITAL_SLUG_IDS:
            doctors_slug, aster_id = _split_slug_id(slug_id)
            existing = db.query(models.AsterHospital).filter(models.AsterHospital.aster_id == aster_id).first()

            # --- hospital detail ---
            if existing and existing.status == "scraped" and not force:
                _log(f"[{aster_id}] {doctors_slug}: hospital detail already scraped, skipping.")
                hospital_row = existing
            else:
                data = engine.scrape_hospital(doctors_slug, aster_id)
                hospital_row = _upsert_hospital(db, aster_id, doctors_slug, data)
                if data.get("ok"):
                    _log(f"[{aster_id}] {doctors_slug}: hospital detail scraped ({hospital_row.name}).")
                else:
                    _log(f"[{aster_id}] {doctors_slug}: hospital detail FAILED — {data.get('error')}", ok=False)
                time.sleep(REQUEST_DELAY_SECONDS)

            # --- doctors ---
            if existing and existing.doctors_status == "scraped" and not force:
                _log(f"[{aster_id}] {doctors_slug}: doctors already scraped ({existing.doctor_count}), skipping.")
                with _lock:
                    _state["processed"] += 1
                continue

            total_added = 0

            def on_page(page_num, doctors, hospital_row=hospital_row):
                nonlocal total_added
                added = _save_doctors_page(db, hospital_row, doctors)
                total_added += added
                _log(f"[{aster_id}] {doctors_slug}: page {page_num} -> {len(doctors)} cards, {added} new.")

            result = engine.scrape_doctors(slug_id, on_page=on_page)
            if result["ok"]:
                hospital_row.doctors_status = "scraped"
                hospital_row.doctor_count = db.query(models.AsterDoctor).filter(
                    models.AsterDoctor.hospital_aster_id == aster_id
                ).count()
                _log(f"[{aster_id}] {doctors_slug}: doctors done — {hospital_row.doctor_count} total "
                     f"({total_added} new this run).")
            else:
                hospital_row.doctors_status = "failed"
                hospital_row.error_detail = result.get("error")
                _log(f"[{aster_id}] {doctors_slug}: doctors FAILED — {result.get('error')}", ok=False)
            db.commit()

            with _lock:
                _state["processed"] += 1
            time.sleep(REQUEST_DELAY_SECONDS)
    finally:
        db.close()
        with _lock:
            _state.update(running=False, finished_at=datetime.utcnow().isoformat())
        _log("Run complete.")


def start_run(force: bool = False) -> dict:
    with _lock:
        if _state["running"]:
            return {"ok": False, "error": "A run is already in progress"}
    threading.Thread(target=_run, args=(force,), daemon=True).start()
    return {"ok": True}


def run_sync(force: bool = False):
    """Blocking variant, for CLI/manual verification runs."""
    _run(force)


def get_report() -> dict:
    db = SessionLocal()
    try:
        hospitals = db.query(models.AsterHospital).order_by(models.AsterHospital.aster_id).all()
        per_hospital = []
        grand_total = 0
        for h in hospitals:
            count = db.query(models.AsterDoctor).filter(models.AsterDoctor.hospital_aster_id == h.aster_id).count()
            grand_total += count
            per_hospital.append({
                "aster_id": h.aster_id, "slug": h.slug, "name": h.name,
                "status": h.status, "doctors_status": h.doctors_status, "doctor_count": count,
            })
        return {"hospitals": per_hospital, "grand_total": grand_total}
    finally:
        db.close()
