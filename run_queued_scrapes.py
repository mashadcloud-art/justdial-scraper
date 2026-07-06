"""
Queue Coordinator for JustDial Scrapers.
Runs scrape_kerala_automobile.py first, and then scrape_kerala_restaurants.py.
Logs execution to jd_queued_run.log.
"""

import subprocess
import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("queue_manager")

def run_script(script_name: str):
    logger.info(f"▶️ Starting queued script: {script_name}")
    python_exe = sys.executable
    cmd = [python_exe, "-u", script_name]
    
    # We open the log file to append output from the script
    log_file = "jd_queued_run.log"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n\n=========================================\n")
        lf.write(f"STARTING QUEUED EXECUTION OF: {script_name}\n")
        lf.write(f"=========================================\n\n")
        lf.flush()
        
        process = subprocess.Popen(
            cmd,
            stdout=lf,
            stderr=subprocess.STDOUT
        )
        process.wait()
        
    if process.returncode == 0:
        logger.info(f"✅ Queued script completed successfully: {script_name}")
    else:
        logger.error(f"❌ Queued script failed with code {process.returncode}: {script_name}")

def main():
    logger.info("🚦 Starting JustDial Scraper Queue Coordinator...")
    
    # Task 1: Automobile & Transport Scraper (resumes where it left off)
    run_script("scrape_kerala_automobile.py")
    
    # Task 2: Restaurants Scraper
    run_script("scrape_kerala_restaurants.py")
    
    logger.info("🏁 All queued scrape tasks have completed!")

if __name__ == "__main__":
    main()
