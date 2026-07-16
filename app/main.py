import sys
import os
import json
import importlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from app.database import engine, Base


# Create tables asynchronously in a background thread to prevent blocking server startup
import threading
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("[DB] Database tables verified.")
    except Exception as e:
        print(f"[DB] Database tables verification deferred: {e}")

    # create_all() only creates missing tables — it won't add new columns to a table that
    # already existed, so newly-added columns on existing models need an explicit ALTER TABLE.
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE scrape_jobs ADD COLUMN log_tail TEXT"))
        print("[DB] Added scrape_jobs.log_tail column.")
    except Exception:
        pass  # column already exists (or table not created yet) — safe to ignore

    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE scrape_jobs ADD COLUMN control VARCHAR(20) DEFAULT 'run'"))
        print("[DB] Added scrape_jobs.control column.")
    except Exception:
        pass  # column already exists (or table not created yet) — safe to ignore

threading.Thread(target=init_db, daemon=True).start()

app = FastAPI(title="JustDial Desktop Scraper API")

# ─── Auto-Start JD Scraper on Server Boot ────────────────────────────────────
@app.on_event("startup")
async def auto_start_jd_scraper():
    """Auto-scraper disabled in production build."""
    pass
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


# ─── Feature modules (app/modules/<name>/) ───────────────────────────────────
# Each module owns its own router.py + service.py + manifest.json. Removing a
# name from this list (or a bug inside that module's router) only drops that
# module's endpoints — the others keep working.
MODULE_NAMES = ["auth", "scraper", "deep_scrape", "dashboard", "export", "module_store"]

def _register_modules(app: FastAPI):
    modules_dir = os.path.join(os.path.dirname(__file__), "modules")
    for name in MODULE_NAMES:
        manifest = {}
        manifest_path = os.path.join(modules_dir, name, "manifest.json")
        try:
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
        except Exception as e:
            print(f"[modules] Could not read manifest for '{name}': {e}")

        try:
            router_module = importlib.import_module(f"app.modules.{name}.router")
            app.include_router(router_module.router)
            print(f"[modules] Loaded '{name}' v{manifest.get('version', '?')} — {manifest.get('description', '')}")
        except Exception as e:
            print(f"[modules] Failed to load '{name}': {e}")

_register_modules(app)
# ─────────────────────────────────────────────────────────────────────────────


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


# --- SERVE FRONTEND STATIC FILES ---
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException

if os.path.exists("ui/dist/client"):
    # Mount the static assets folder (CSS, JS)
    app.mount("/assets", StaticFiles(directory="ui/dist/client/assets"), name="assets")

    # Catch-all route to serve the React SPA index.html
    @app.get("/{rest_of_path:path}")
    def serve_frontend(rest_of_path: str):
        # Allow API and media directories to bypass
        if rest_of_path.startswith("api/") or rest_of_path.startswith("images/") or rest_of_path.startswith("scraped_images/") or rest_of_path.startswith("uploaded_images/"):
            raise HTTPException(status_code=404, detail="Not found")

        index_path = "ui/dist/client/index.html"
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="Frontend build index.html not found.", status_code=404)
else:
    @app.get("/")
    def root():
        return {"status": "running", "message": "JustDial API is ready!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=False)
