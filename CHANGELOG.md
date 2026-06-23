# JustDial Pro Scraper - Application Roadmap & History

This document maps out the **entire architecture** of the JustDial Scraper application, explaining how all the moving parts work together, followed by a history of major updates.

---

## 🏗️ Application Architecture & Route Map

The application is broken down into three main components: The Frontend (UI), The Backend (FastAPI), and the Database (Supabase).

### 1. The Frontend UI (`/ui` folder)
The frontend is a modern React application built with Vite and styled using Tailwind CSS. 
- **Main Dashboard (`ui/src/routes/index.tsx`)**: This is the control center. It contains the Scraper controls (selecting state, city, category) and the Dashboard table (where you view, search, and manage all scraped listings).
- **Search & Filtering**: The dashboard UI is designed to only load 50 items at a time to prevent crashing. It sends search queries (like "Salon") directly to the backend to search the entire database instantly.
- **Port**: Typically runs on port `8081` locally, or built into static HTML/JS for the live server.

### 2. The Backend API (`/app` folder)
The backend is powered by FastAPI (Python) and serves as the bridge between the UI, the scrapers, and the database.
- **API Endpoints (`app/api/sync.py`)**: Handles all requests from the UI. It receives commands to start scraping, fetches listings for the dashboard, and handles the bulk search queries.
- **The Scraper Engines (`app/scraper/`)**: The core logic that extracts data.
  - `playwright_scraper.py` / `desktop_scraper.py`: Uses headless browsers to navigate JustDial and extract data.
  - `api_scraper.py`: Interacts directly with internal APIs for faster data extraction.
  - `emulator_parser.py`: Extracts raw JSON data if the scraper is running through an Android emulator proxy.
- **Data Normalizers**:
  - `location_correction.py`: Uses Nominatim/geopy reverse-geocoding to convert raw GPS coordinates into the correct District, City, and State.
  - `category_normalizer.py`: Groups hundreds of messy subcategories (like "Massage Centers" and "Bridal Makeup") into clean parent categories (like "Beauty & Spas").
- **Port**: Typically runs on port `8000`.

### 3. The Database (Supabase PostgreSQL)
All scraped data is permanently stored in a remote Supabase PostgreSQL database.
- **Connection**: Managed in `app/database.py` and `app/models.py`.
- **Tables**: Includes `listings` (the core businesses), `menu_items`, `amenities`, and `images`.

---

## 📜 Version History & Changelog

### [Version 3.1] - Performance, Search, & Data Integrity Updates
*Date: June 2026*

- **Dashboard Speed (Browser Crash Fix)**: The UI previously crashed by attempting to load 13,000+ listings at once. Fixed by limiting the initial API fetch to 50 items.
- **Global Server-Side Search**: Added a Search Bar to the dashboard. Modified the backend API (`sync.py`) to scan `name`, `category`, `address`, `phone`, and `district` directly in the database. This allows cross-category lookup (e.g., finding "Salon" within the "Spa" category).
- **Location Correction Engine**: Built a reverse-geocoding engine (`location_correction.py`) to automatically fix incorrect or missing District/City locations using latitude and longitude coordinates.
- **Bulk Cleanup Script**: Added `scratch/fix_all_locations.py` to retroactively repair the 13,000+ bad locations already saved in Supabase.
- **Category Normalization**: Grouped unstructured subcategories into clean parent groups for better sorting.

### [Version 3.0] - Supabase Migration & Core Structure
- Upgraded the entire database system to use Supabase (PostgreSQL) instead of local SQLite.
- Segregated categories and established state/place mappings.
- Built the foundational FastAPI backend and React frontend.

---

## 🛠️ Server Deployment Cheatsheet

When updates are pushed to the GitHub repository, run these commands on your Ubuntu Server (`ubuntu@ph-uae`) to apply them to your live website:

```bash
# 1. Enter the project folder
cd "/home/ubuntu/Scapre for thozil"

# 2. Stash any conflicting local server changes and pull the new code
git stash
git pull

# 3. Rebuild the frontend UI
cd ui
npm install
npm run build
cd ..

# 4. Restart your Python backend (e.g., your server-app-manager or nohup process)
```
