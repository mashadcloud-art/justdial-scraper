#!/bin/bash
# Scrape the remaining 7 districts of Rajasthan
for dist in "Churu" "Dausa" "Dholpur" "Dungarpur" "Hanumangarh" "Jaipur" "Jaisalmer"; do
    echo "=== Starting $dist at $(date) ==="
    python3 -u jd_api_scraper.py --district "$dist" --category "Rentals" --pages 10 --subcategories --use-proxy
done
