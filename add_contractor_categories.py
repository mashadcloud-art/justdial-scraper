"""
Script to insert the extracted Contractor subcategories into the Supabase database Categories table.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.database import engine, SessionLocal
from app import models
from sqlalchemy import text

categories_list = [
    ("Carpentry Contractors", "https://www.justdial.com/Ernakulam/Carpentry-Contractors-in-Kochi/nct-10080646"),
    ("Civil Contractors", "https://www.justdial.com/Ernakulam/Civil-Contractors-in-Kochi/nct-10100369"),
    ("Electrical Contractors", "https://www.justdial.com/Ernakulam/Electrical-Contractors-in-Kochi/nct-10183194"),
    ("Flooring Contractors", "https://www.justdial.com/Ernakulam/Flooring-Contractors-in-Kochi/nct-10211226"),
    ("Furniture Contractors", "https://www.justdial.com/Ernakulam/Furniture-Contractors-in-Kochi/nct-10219641"),
    ("Painting Contractors", "https://www.justdial.com/Ernakulam/Painting-Contractors-in-Kochi/nct-10350809"),
    ("Plumbing Contractors", "https://www.justdial.com/Ernakulam/Plumbing-Contractors-in-Kochi/nct-10378056"),
    ("Borewell Contractors", "https://www.justdial.com/Ernakulam/Borewell-Contractors-in-Kochi/nct-10053824"),
    ("Building Contractors", "https://www.justdial.com/Ernakulam/Building-Contractors-in-Kochi/nct-10059338"),
    ("Carpet Contractors", "https://www.justdial.com/Ernakulam/Carpet-Contractors-in-Kochi/nct-10080757"),
    ("Construction Contractors", "https://www.justdial.com/Ernakulam/Construction-Contractors-in-Kochi/nct-10128276"),
    ("Drainage Contractors", "https://www.justdial.com/Ernakulam/Drainage-Contractors-in-Kochi/nct-10171640"),
    ("Drilling Contractors", "https://www.justdial.com/Ernakulam/Drilling-Contractors-in-Kochi/nct-10172821"),
    ("Elevator Contractors", "https://www.justdial.com/Ernakulam/Elevator-Contractors-in-Kochi/nct-10186312"),
    ("Fabrication Contractors", "https://www.justdial.com/Ernakulam/Fabrication-Contractors-in-Kochi/nct-10197795"),
    ("False Ceiling Contractors", "https://www.justdial.com/Ernakulam/False-Ceiling-Contractors-in-Kochi/nct-10198933"),
    ("Fire Fighting Contractors", "https://www.justdial.com/Ernakulam/Firefighting-Contractors-in-Kochi/nct-10207979"),
    ("Garden Contractors", "https://www.justdial.com/Ernakulam/Garden-Contractors-in-Kochi/nct-10222744"),
    ("Interior Decorators", "https://www.justdial.com/Ernakulam/Interior-Decorators-in-Kochi/nct-10272268"),
    ("Labour Contractors", "https://www.justdial.com/Ernakulam/Labour-Contractors-in-Kochi/nct-10291693"),
    ("Pipeline Contractors", "https://www.justdial.com/Ernakulam/Pipeline-Contractors-in-Kochi/nct-10370044"),
    ("Pop Contractors", "https://www.justdial.com/Ernakulam/Pop-Contractors-in-Kochi/nct-10891377"),
    ("Road Construction Contractors", "https://www.justdial.com/Ernakulam/Road-Construction-Contractors-in-Kochi/nct-10411348"),
    ("Roofing Contractors", "https://www.justdial.com/Ernakulam/Roofing-Contractors-in-Kochi/nct-10413387"),
    ("Swimming Pool Construction Contractors", "https://www.justdial.com/Ernakulam/Swimming-Pool-Contractors-in-Kochi/nct-11481308"),
    ("Tiling Contractors", "https://www.justdial.com/Ernakulam/Tiling-Contractors-in-Kochi/nct-10890842"),
    ("Wall Paper Contractors", "https://www.justdial.com/Ernakulam/Wall-Paper-Contractors-in-Kochi/nct-10525839"),
    ("Waterproofing Contractors", "https://www.justdial.com/Ernakulam/Waterproofing-Contractors-in-Kochi/nct-10533854"),
    ("Welding Contractors", "https://www.justdial.com/Ernakulam/Welding-Contractors-in-Kochi/nct-10536536"),
]

def add_categories():
    db = SessionLocal()
    print("[OK] Connected to database.")
    
    parent = "Civil Contractors"
    inserted = 0
    skipped = 0
    
    for name, url in categories_list:
        # Check if category already exists
        existing = db.query(models.Category).filter_by(name=name).first()
        if not existing:
            new_cat = models.Category(
                name=name,
                parent_category=parent,
                jd_url=url,
                is_active=True
            )
            db.add(new_cat)
            inserted += 1
        else:
            skipped += 1
            
    db.commit()
    db.close()
    print(f"[COMPLETE] Inserted {inserted} new category entries, skipped {skipped} existing ones.")

if __name__ == "__main__":
    add_categories()
