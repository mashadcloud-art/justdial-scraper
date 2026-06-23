# Changelog & Updates Roadmap

This document serves as a history of major structural updates, data cleanup engines, and UI fixes applied to the JustDial Scraper project. 

## [Version 3.1] - Performance & Data Integrity Update

### 1. Dashboard Speed & Performance (Browser Crash Fix)
- **Previous Issue:** The dashboard attempted to fetch all 13,000+ database rows on load, causing the browser to crash or freeze.
- **Fix:** Changed the default API fetch limit in the dashboard UI (`index.tsx`) to 50 items. The dashboard now loads instantly.

### 2. Global Server-Side Search
- **Previous Issue:** The dashboard lacked a text search bar, and client-side filtering only searched the visible rows. Cross-category lookup (e.g., finding "Salon" in a "Spa" category) was impossible.
- **Fix:** Added a Search Bar to the dashboard. Modified the backend API (`app/api/sync.py`) to accept a `search` parameter that rapidly scans `name`, `category`, `subcategory`, `address`, `phone`, and `district` directly from the database.

### 3. Location Correction Engine (Reverse Geocoding)
- **Previous Issue:** Scraped locations (District, City, Area) were often wrong, mismatched, or missing.
- **Fix:** Built a reverse-geocoding engine (`app/scraper/location_correction.py`) using `geopy` and the Nominatim API. 
- **Auto-Correction:** Hooked this engine into the scraper upload pipeline (`app/api/sync.py`). Any newly scraped listing with latitude/longitude coordinates is now automatically verified and its District/City/State is corrected before saving to the database.

### 4. Bulk Data Cleanup Script
- **Feature:** Added a standalone script `scratch/fix_all_locations.py` to retroactively fix the existing 13,000+ bad locations already in the database.
- **Usage:** Run `python scratch/fix_all_locations.py` from the local terminal. It respects the 1-request-per-second API limit and safely cleans up old data in the background.

### 5. Category Normalization
- **Feature:** Added `app/scraper/category_normalizer.py` to group hundreds of random subcategories into clean parent groups (e.g., "Unisex Salons" and "Massage Centres" both map to "Beauty & Spas").

---

## 🛠️ Server Deployment Cheatsheet
When updates are pushed to the GitHub repository, use these commands on the Ubuntu Server (`ubuntu@ph-uae`) to apply them to the live site:

```bash
# 1. Go to the project folder
cd "/home/ubuntu/Scapre for thozil"

# 2. Stash any conflicting local changes and pull the new code
git stash
git pull

# 3. Rebuild the frontend UI
cd ui
npm install
npm run build
cd ..

# 4. Restart the backend (e.g., your python server-app-manager process)
# 5. Refresh the live website
```
