import json
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.database import SessionLocal
from app import models

def main():
    print("Connecting to database...")
    db = SessionLocal()
    try:
        job = db.query(models.DeepScrapeJob).order_by(models.DeepScrapeJob.created_at.desc()).first()
        if not job:
            print("No jobs found in deep_scrape_jobs table.")
            return
            
        print("="*60)
        print(f"Job ID: {job.job_id}")
        print(f"URL: {job.url}")
        print(f"Status: {job.status}")
        print(f"Completed Subcategories: {job.completed_subcategories} / {job.total_subcategories}")
        print("="*60)
        print("Log Tail:")
        if job.log_tail:
            logs = json.loads(job.log_tail)
            for line in logs:
                print(line)
        else:
            print("No logs recorded for this job.")
        print("="*60)
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
