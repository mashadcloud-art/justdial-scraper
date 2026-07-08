import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from app.database import engine, Base
from app.api import sync, categories, pincodes  # 🟢 ADDED CATEGORIES AND PINCODES HERE
from app.api import gmaps as gmaps_api  # 🟢 Google Maps scraper
from app.api import simple_scrape as simple_scrape_api  # 🟢 Simple one-shot scraper


Base.metadata.create_all(bind=engine)

app = FastAPI(title="JustDial Desktop Scraper API")

# ─── Auto-Start JD Scraper on Server Boot ────────────────────────────────────
import subprocess
import json as _json

_AUTO_SCRAPE_CONFIG = "auto_scrape_config.json"
_DEFAULT_SCRAPE_CONFIG = {
    "enabled": True,
    "district": "Kannur",
    "category": "Restaurants",
    "pages": 10
}

@app.on_event("startup")
async def auto_start_jd_scraper():
    """Automatically start the JustDial scraper on server boot if enabled."""
    config = _DEFAULT_SCRAPE_CONFIG.copy()
    if os.path.exists(_AUTO_SCRAPE_CONFIG):
        try:
            with open(_AUTO_SCRAPE_CONFIG) as f:
                config.update(_json.load(f))
        except Exception:
            pass

    if not config.get("enabled", True):
        print("[AutoScrape] Disabled via config. Skipping auto-start.")
        return

    district = config["district"]
    category = config["category"]
    pages = config.get("pages", 10)
    log_file = f"jd_{district.lower()}_{category.lower().replace(' ', '_')}.log"

    subcategories = config.get("subcategories", False)

    print(f"[AutoScrape] [STARTING] Auto-starting JD scraper: {district} / {category} (pages={pages}, subcategories={subcategories}) -> {log_file}")
    try:
        python_exe = sys.executable
        cmd = [
            python_exe, "-u", "jd_api_scraper.py",
            "--district", district,
            "--category", category,
            "--pages", str(pages)
        ]
        if subcategories:
            cmd.append("--subcategories")
            
        with open(log_file, "a", encoding="utf-8") as lf:
            subprocess.Popen(
                cmd,
                stdout=lf,
                stderr=subprocess.STDOUT
            )
        print(f"[AutoScrape] [OK] Scraper launched. Logs -> {log_file}")
    except Exception as e:
        print(f"[AutoScrape] [ERROR] Failed to auto-start scraper: {e}")
# ─────────────────────────────────────────────────────────────────────────────



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import Request, Response
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

app.include_router(sync.router, prefix="/api/v1")
app.include_router(categories.router)
app.include_router(pincodes.router)
app.include_router(gmaps_api.router)  # Google Maps scraper
app.include_router(simple_scrape_api.router)  # Simple one-shot scraper


if os.path.exists("data/uploaded_images"):
    app.mount("/uploaded_images", StaticFiles(directory="data/uploaded_images"), name="uploaded_images")
    app.mount("/api/uploaded_images", StaticFiles(directory="data/uploaded_images"), name="api_uploaded_images")
    app.mount("/api/v1/uploaded_images", StaticFiles(directory="data/uploaded_images"), name="api_v1_uploaded_images")
    app.mount("/api/data/uploaded_images", StaticFiles(directory="data/uploaded_images"), name="api_data_uploaded_images")
elif os.path.exists("uploaded_images"):
    app.mount("/uploaded_images", StaticFiles(directory="uploaded_images"), name="uploaded_images")
    app.mount("/api/uploaded_images", StaticFiles(directory="uploaded_images"), name="api_uploaded_images")
    app.mount("/api/v1/uploaded_images", StaticFiles(directory="uploaded_images"), name="api_v1_uploaded_images")

if os.path.exists("scraped_images"):
    app.mount("/scraped_images", StaticFiles(directory="scraped_images"), name="scraped_images")
    app.mount("/api/scraped_images", StaticFiles(directory="scraped_images"), name="api_scraped_images")
    app.mount("/api/v1/scraped_images", StaticFiles(directory="scraped_images"), name="api_v1_scraped_images")

if os.path.exists("simple_scrape_results"):
    app.mount("/simple_scrape_results", StaticFiles(directory="simple_scrape_results"), name="simple_scrape_results")
    app.mount("/api/v1/simple_scrape_results", StaticFiles(directory="simple_scrape_results"), name="api_simple_scrape_results")
    app.mount("/api/simple_scrape_results", StaticFiles(directory="simple_scrape_results"), name="api_short_simple_scrape_results")

from fastapi.responses import HTMLResponse
@app.get("/images.html", response_class=HTMLResponse)
@app.get("/api/v1/images.html", response_class=HTMLResponse)
@app.get("/api/images", response_class=HTMLResponse)
@app.get("/api/image", response_class=HTMLResponse)
@app.get("/api/img", response_class=HTMLResponse)
def get_images_page():
    if os.path.exists("images.html"):
        with open("images.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="images.html not found")

@app.get("/", response_class=HTMLResponse)
@app.get("/scraper", response_class=HTMLResponse)
@app.get("/scraper.html", response_class=HTMLResponse)
def get_scraper_page():
    if os.path.exists("scraper.html"):
        with open("scraper.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    # fallback JSON
    from fastapi.responses import JSONResponse
    return JSONResponse({"status": "running", "message": "JustDial API is ready! Open /scraper.html"})



from app.database import SessionLocal
from app import models
from sqlalchemy import func

import subprocess
import sys
import psutil
from fastapi import HTTPException

@app.get("/api/v1/daemon/status")
def get_daemon_status():
    is_running = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            if any('scrape_background_images.py' in part for part in cmd):
                is_running = True
                break
        except Exception:
            pass

    db = SessionLocal()
    try:
        total_listings = db.query(models.Listing).count()
        pending_count = db.query(models.Listing.id).outerjoin(models.ListingImage).group_by(models.Listing.id).having(func.count(models.ListingImage.id) <= 1).count()
        completed_count = total_listings - pending_count
    except Exception as e:
        total_listings = 0
        pending_count = 0
        completed_count = 0
        print(f"Error querying daemon stats: {e}")
    finally:
        db.close()

    logs = []
    log_files = ["bg_scraper_logs.txt", "cloud_bg_scraper.log"]
    for f_name in log_files:
        if os.path.exists(f_name):
            try:
                with open(f_name, "r", encoding="utf-8", errors="replace") as lf:
                    lines = lf.readlines()
                    logs = [line.strip() for line in lines[-25:]]
                break
            except Exception:
                pass
                
    return {
        "total_listings": total_listings,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "is_running": is_running,
        "logs": logs
    }

@app.post("/api/v1/daemon/start")
def start_daemon():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            if any('scrape_background_images.py' in part for part in cmd):
                return {"status": "already_running"}
        except Exception:
            pass

    try:
        python_exe = sys.executable
        log_file_path = "bg_scraper_logs.txt"
        log_file = open(log_file_path, "a", encoding="utf-8")
        subprocess.Popen(
            [python_exe, "-u", "app/scraper/scrape_background_images.py", "--no-shutdown"],
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
        return {"status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start daemon: {e}")

@app.post("/api/v1/daemon/stop")
def stop_daemon():
    stopped = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            if any('scrape_background_images.py' in part for part in cmd):
                proc.terminate()
                stopped = True
        except Exception:
            pass
    return {"status": "stopped" if stopped else "not_running"}

@app.get("/")
def root():
    return {"status": "running", "message": "JustDial API is ready!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)