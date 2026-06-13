import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from app.database import engine, Base
from app.api import sync, categories  # 🟢 ADDED CATEGORIES HERE

Base.metadata.create_all(bind=engine)

app = FastAPI(title="JustDial Desktop Scraper API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sync.router)
app.include_router(categories.router)  #  ADDED CATEGORIES ROUTER HERE

if os.path.exists("uploaded_images"):
    app.mount("/uploaded_images", StaticFiles(directory="uploaded_images"), name="uploaded_images")

@app.get("/")
def root():
    return {"status": "running", "message": "JustDial API is ready!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)