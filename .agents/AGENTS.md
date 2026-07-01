# JustDial Scraper Project - AI Memory & Rules

## How to Run the App
- **DO NOT** try to run `python`, `py`, or `streamlit` directly unless explicitly asked.
- **ALWAYS** launch the main application by executing `wscript "Launch JustDial Scraper v2.0.vbs"`.
- The main application consists of a FastAPI backend and a Vite web frontend. 

## Recent Architectural Changes
- **Module Shop (Plugin Architecture)**: We recently added a dynamic plugin system.
  - The core engine is located in `core/plugin_manager.py` and `core/config.json`.
  - Plugins are stored in the `modules/` directory.
  - Currently, the "Module Shop" UI is only implemented in the Streamlit dashboard (`frontend.py`), NOT in the main Vite web app.
- **Hybrid Google Maps Cloud Scraper**: We built a "Cloud Job Queue" architecture for Google Maps scraping.
  - **Local Fast Scraper**: `scrape_gmaps_general.py` quickly scrapes text/details and 1 image.
  - **Deep Image Daemon**: `app/scraper/scrape_background_images.py` scans the DB for listings with <= 1 image and uses an advanced Playwright scroll script to extract up to 50 gallery images.
  - **Cloud Worker (`cloud_job_worker.py`)**: A 24/7 daemon intended for an Ubuntu cloud server. It listens to the `scraper_jobs` table in Supabase. When a user clicks "☁️ Send Full Scrape to Cloud" in the local Streamlit dashboard, a job is inserted. The cloud worker then automatically launches both scrapers to perform heavy scraping off-device.

## General Guidelines
- Check this file and `CHANGELOG.md` before making assumptions about how the app runs.
- Python path for this project is specifically: `C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe` (or `pythonw.exe`).
