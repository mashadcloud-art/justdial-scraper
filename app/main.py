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

app.include_router(sync.router, prefix="/api/v1")
app.include_router(categories.router)
app.include_router(gmaps_api.router)  # Google Maps scraper

if os.path.exists("data/uploaded_images"):
    app.mount("/uploaded_images", StaticFiles(directory="data/uploaded_images"), name="uploaded_images")
elif os.path.exists("uploaded_images"):
    app.mount("/uploaded_images", StaticFiles(directory="uploaded_images"), name="uploaded_images")

if os.path.exists("scraped_images"):
    app.mount("/scraped_images", StaticFiles(directory="scraped_images"), name="scraped_images")

@app.get("/")
def root():
    return {"status": "running", "message": "JustDial API is ready!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)