import sys
import os
import time
import subprocess
from datetime import datetime

# Add parent directory to path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import SessionLocal
from app import models

# Assuming python executable is standard 'python3' on the Ubuntu server
PYTHON_EXE = "python3"

def main():
    print("============================================================")
    print("☁️ CLOUD JOB WORKER (DAEMON MODE)")
    print("============================================================")
    print("Running continuously. Watching Supabase for 'pending' jobs...")
    
    # We create a new session per loop to avoid stale data
    
    while True:
        try:
            db = SessionLocal()
            
            # Find the oldest pending job
            job = db.query(models.ScraperJob).filter(models.ScraperJob.status == "pending").order_by(models.ScraperJob.created_at.asc()).first()
            
            if not job:
                db.close()
                time.sleep(10) # Wait 10 seconds before checking again
                continue
                
            print(f"\n[JOB DETECTED] ID: {job.id} - Scraping {job.query} in {job.district}")
            
            # Mark as running
            job.status = "running"
            db.commit()
            
            # Extract arguments
            district = job.district
            query = job.query
            category = job.category
            normalized_category = job.normalized_category
            max_photos = job.max_photos
            
            db.close() # Close session before starting long-running sub-processes
            
            # Start Background Image Scraper
            print("  -> Starting Background Image Scraper Daemon...")
            bg_scraper = subprocess.Popen(
                [PYTHON_EXE, "-u", "app/scraper/scrape_background_images.py", "--category", category],
                stdout=open("cloud_bg_scraper.log", "w"),
                stderr=subprocess.STDOUT
            )
            
            # Start Fast Scraper
            print("  -> Starting Fast Scraper...")
            fast_cmd = [
                PYTHON_EXE, "-u", "scrape_gmaps_general.py",
                "--district", district,
                "--query", query,
                "--category", category,
                "--normalized-category", normalized_category,
                "--max-photos", "1",
                "--live"
            ]
            
            fast_scraper = subprocess.Popen(
                fast_cmd,
                stdout=open("cloud_fast_scraper.log", "w"),
                stderr=subprocess.STDOUT
            )
            
            # Wait for Fast Scraper to finish but poll for cancel signals
            print("  -> Waiting for Fast Scraper to complete...")
            
            job_cancelled = False
            while fast_scraper.poll() is None:
                # Open DB to check for cancel signal
                cancel_db = SessionLocal()
                cancel_job = cancel_db.query(models.ScraperJob).filter(models.ScraperJob.status == "cancel").first()
                if cancel_job:
                    print("\n[!] CANCEL SIGNAL RECEIVED! Terminating cloud scrapers...")
                    fast_scraper.terminate()
                    bg_scraper.terminate()
                    
                    # Update statuses
                    job_cancelled = True
                    cancel_job.status = "completed"
                    cancel_db.commit()
                    cancel_db.close()
                    break
                
                cancel_db.close()
                time.sleep(5)
                
            if job_cancelled:
                print("  -> Scrapers forcefully stopped.")
            else:
                print("  -> Fast Scraper finished naturally!")
            
            # The background scraper runs as a daemon and automatically shuts down after 2 minutes of inactivity.
            # We don't need to explicitly kill it unless it was cancelled.
            
            # Re-open DB to mark job as completed or cancelled
            db = SessionLocal()
            # Fetch the job again to avoid stale object errors
            job = db.query(models.ScraperJob).filter(models.ScraperJob.id == job.id).first()
            if job:
                job.status = "cancelled" if job_cancelled else "completed"
                job.completed_at = datetime.utcnow()
                db.commit()
            db.close()
            
            print(f"[JOB COMPLETE] Job {job.id} finished successfully. Resuming polling...")
            
        except Exception as e:
            print(f"[ERROR] Worker encountered an error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
