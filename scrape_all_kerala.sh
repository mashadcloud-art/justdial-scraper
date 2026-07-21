#!/bin/bash
DISTRICTS=("Kasaragod" "Kannur" "Kozhikode" "Malappuram" "Thrissur" "Palakkad" "Ernakulam" "Idukki" "Kottayam" "Alappuzha" "Pathanamthitta" "Kollam" "Thiruvananthapuram" "Wayanad")
CATEGORIES=("Restaurants" "Hotels" "Hospitals" "Doctors" "Beauty Spa" "Education" "Pharmacies" "Lawyers" "Estate Agent" "Contractors" "Gym" "Driving Schools" "Packers and Movers" "Courier Service" "Pet Shops" "Electricians" "Plumbers" "Event Organisers" "Loans" "Supermarkets" "PG Hostels" "Fast Food" "Bakeries" "Schools" "Colleges" "General Physicians" "Dentists" "Gynaecologists" "Paediatricians" "Dermatologists")

for category in "${CATEGORIES[@]}"; do
  for district in "${DISTRICTS[@]}"; do
    echo "[$(date)] Scraping: $category in $district"
    cd ~/justdial-scraper && python jd_api_scraper.py --district "$district" --category "$category" --pages 10
    sleep 2
  done
done
echo "ALL DONE!"
