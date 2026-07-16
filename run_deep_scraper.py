import argparse
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.database import SessionLocal
from app import models
from app.scraper.deep_category_scraper import run_deep_scrape_job

def main():
    parser = argparse.ArgumentParser(description="JustDial Deep Category Scraper (CLI)")
    parser.add_argument("--url", required=True, help="JustDial category URL (e.g. https://www.justdial.com/Kasaragod/Hospitals/nct-10253670)")
    parser.add_argument("--mode", default="district", choices=["district", "state"], help="Scrape mode: 'district' (local city only) or 'state' (all Kerala districts)")
    args = parser.parse_args()

    db = SessionLocal()
    job_id = uuid.uuid4().hex[:12]
    
    # Create the job in the database
    job = models.DeepScrapeJob(
        job_id=job_id,
        url=args.url,
        mode=args.mode,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.close()

    print(f"Starting Deep Scrape Job {job_id}...")
    print(f"URL: {args.url}")
    print(f"Mode: {args.mode}")
    print("----------------------------------------")

    # Run the job synchronously in the foreground for CLI output
    run_deep_scrape_job(job_id, args.url, args.mode)

if __name__ == "__main__":
    main()
