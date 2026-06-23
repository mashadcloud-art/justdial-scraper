import json
from app.scraper.playwright_scraper import preview_page

results = preview_page("Idukki", "Fast Food", "Fast Food", 1)
print("Preview results:", json.dumps(results, indent=2))
