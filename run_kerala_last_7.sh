#!/bin/bash
# Scrape the last 7 districts of Kerala
for dist in "Wayanad" "Thrissur" "Thiruvananthapuram" "Pathanamthitta" "Palakkad" "Kollam" "Malappuram"; do
    echo "=== Starting $dist at $(date) ==="
    python3 -u jd_api_scraper.py --district "$dist" --category "Rentals" --pages 10 --subcategories --use-proxy
done
