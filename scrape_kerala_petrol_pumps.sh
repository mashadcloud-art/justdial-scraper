#!/bin/bash
# ============================================================
# Kerala Petrol Pumps - Full State Google Maps Scraper
# Run on cloud server: ubuntu@ph-uae
# Usage: bash scrape_kerala_petrol_pumps.sh
# ============================================================

PYTHON="python3"
SCRIPT="scrape_gmaps_general.py"
QUERY="petrol pumps"
CATEGORY="Petrol Pumps"
NORM_CATEGORY="Petrol Pumps"
MAX_PHOTOS=1

LOG="kerala_petrol_pumps_cloud.log"

DISTRICTS=(
  "Kasaragod"
  "Kannur"
  "Wayanad"
  "Kozhikode"
  "Malappuram"
  "Palakkad"
  "Thrissur"
  "Ernakulam"
  "Idukki"
  "Kottayam"
  "Alappuzha"
  "Pathanamthitta"
  "Kollam"
  "Thiruvananthapuram"
)

echo "============================================================" | tee -a $LOG
echo " Kerala Petrol Pumps Scraper - Started: $(date)" | tee -a $LOG
echo " Total districts: ${#DISTRICTS[@]}" | tee -a $LOG
echo "============================================================" | tee -a $LOG

for i in "${!DISTRICTS[@]}"; do
  DISTRICT="${DISTRICTS[$i]}"
  echo "" | tee -a $LOG
  echo "--- District $((i+1))/${#DISTRICTS[@]}: $DISTRICT ---" | tee -a $LOG
  echo "Started: $(date)" | tee -a $LOG

  $PYTHON -u $SCRIPT \
    --district "$DISTRICT" \
    --query "$QUERY" \
    --category "$CATEGORY" \
    --normalized-category "$NORM_CATEGORY" \
    --max-photos $MAX_PHOTOS \
    --live 2>&1 | tee -a $LOG

  echo "Finished $DISTRICT at $(date). Sleeping 10s..." | tee -a $LOG
  sleep 10
done

echo "" | tee -a $LOG
echo "============================================================" | tee -a $LOG
echo " ALL DONE! Completed at: $(date)" | tee -a $LOG
echo "============================================================" | tee -a $LOG
