import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from app.database import engine, Base
from app.api import sync, categories  # 🟢 ADDED CATEGORIES HERE
from app.api import gmaps as gmaps_api  # 🟢 Google Maps scraper

Base.metadata.create_all(bind=engine)

app = FastAPI(title="JustDial Desktop Scraper API")

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
app.include_router(gmaps_api.router)  # Google Maps scraper

if os.path.exists("data/uploaded_images"):
    app.mount("/uploaded_images", StaticFiles(directory="data/uploaded_images"), name="uploaded_images")
elif os.path.exists("uploaded_images"):
    app.mount("/uploaded_images", StaticFiles(directory="uploaded_images"), name="uploaded_images")

if os.path.exists("scraped_images"):
    app.mount("/scraped_images", StaticFiles(directory="scraped_images"), name="scraped_images")

if os.path.exists("simple_scrape_results"):
    app.mount("/simple_scrape_results", StaticFiles(directory="simple_scrape_results"), name="simple_scrape_results")

from fastapi.responses import HTMLResponse
@app.get("/images.html", response_class=HTMLResponse)
def get_images_page():
    if os.path.exists("images.html"):
        with open("images.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="images.html not found")

from app.database import SessionLocal
from app import models
from sqlalchemy import func

@app.get("/api/v1/daemon/status")
def get_daemon_status():
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
        "logs": logs
    }

@app.get("/")
def root():
    return {"status": "running", "message": "JustDial API is ready!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)