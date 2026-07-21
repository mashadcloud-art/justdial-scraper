"""
import_aster_doctors_to_listings.py
Imports doctor profiles from aster_merged.json directly into the main `listings` table
so they appear on your web dashboard UI (scrapper.mashad.shop)!
"""

import os
import json
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

JSON_PATH = r"C:\Users\PC\Desktop\aster_merged.json"

LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "justdial.db")
LOCAL_URL = f"sqlite:///{LOCAL_DB_PATH.replace(os.sep, '/')}"

SUPABASE_URL = "postgresql://postgres:HEERnuh%402025@db.qdsjbfhjzyypfyryjqxp.supabase.co:5432/postgres"

def main():
    print("=" * 60)
    print("  IMPORTING DOCTORS TO MAIN LISTINGS (DASHBOARD UI)  ")
    print("=" * 60)

    if not os.path.exists(JSON_PATH):
        print(f"❌ Error: File not found at {JSON_PATH}")
        return

    with open(JSON_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    print(f"Found {len(data)} total records to import into `listings`.\n")

    os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)
    local_engine = create_engine(LOCAL_URL)
    from app.models import Base
    Base.metadata.create_all(bind=local_engine)
    LocalSession = sessionmaker(bind=local_engine)
    local_db = LocalSession()

    # Connect Cloud
    cloud_db = None
    try:
        cloud_engine = create_engine(SUPABASE_URL, pool_pre_ping=True)
        Base.metadata.create_all(bind=cloud_engine)
        CloudSession = sessionmaker(bind=cloud_engine)
        cloud_db = CloudSession()
        print("Connected to Supabase successfully!")
    except Exception as e:
        print(f"⚠️ Warning: Could not connect to Supabase: {e}")

    count_local = 0
    count_cloud = 0

    for idx, item in enumerate(data, 1):
        aster_uuid = item.get("id")
        user_info = item.get("user") or {}

        doc_name = item.get("name") or f"Dr. {user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
        qualification = item.get("qualification", "").strip()

        phone = user_info.get("phone", "")
        if phone and not phone.startswith("+"):
            phone = f"+91 {phone}"

        branches_info = item.get("branches_info") or []
        cities = list(set(b.get("city") for b in branches_info if b.get("city")))
        district = cities[0] if cities else "Kerala"

        branches_list = item.get("branches") or []
        branch_name = branches_list[0] if branches_list else "Aster Hospital"

        specialities_list = item.get("specialities") or []
        speciality = specialities_list[0] if specialities_list else "Doctors"

        address = f"{branch_name}, {district}"
        profile_pic = item.get("profile_pic") or item.get("external_profile_pic") or ""

        # Construct Listing dictionary with CLEAN name
        listing_dict = {
            "name": doc_name,
            "address": address,
            "phone": phone,
            "whatsapp": phone,
            "jd_url": f"https://asterhealth.com/doctor/{aster_uuid}",
            "category": "Doctors",
            "subcategory": speciality,
            "normalized_category": "Hospitals & Doctors",
            "opening_hours": "09:00 AM - 05:00 PM",
            "district": district,
            "place": district,
            "state": "Kerala" if district in ["Kozhikode", "Kochi", "Kannur", "Malappuram", "Thiruvananthapuram", "Wayand", "Palakkad"] else "Karnataka",
            "scraped_at": datetime.utcnow()
        }

        # 1. Insert into local SQLite listings
        check_local = local_db.execute(
            text("SELECT id FROM listings WHERE name = :name AND phone = :phone"),
            {"name": listing_dict["name"], "phone": listing_dict["phone"]}
        ).fetchone()

        if not check_local:
            res = local_db.execute(text("""
                INSERT INTO listings (name, address, phone, whatsapp, jd_url, category, subcategory, normalized_category, opening_hours, district, place, state, scraped_at)
                VALUES (:name, :address, :phone, :whatsapp, :jd_url, :category, :subcategory, :normalized_category, :opening_hours, :district, :place, :state, :scraped_at)
            """), listing_dict)
            listing_id = res.lastrowid
            
            if listing_id:
                if profile_pic:
                    local_db.execute(text("""
                        INSERT INTO listing_images (listing_id, image_path, category, is_primary)
                        VALUES (:listing_id, :image_path, 'doctor_photo', 1)
                    """), {"listing_id": listing_id, "image_path": profile_pic})

                if qualification:
                    local_db.execute(text("""
                        INSERT INTO amenities (listing_id, category, value)
                        VALUES (:listing_id, 'Qualification', :value)
                    """), {"listing_id": listing_id, "value": qualification})

                if speciality:
                    local_db.execute(text("""
                        INSERT INTO amenities (listing_id, category, value)
                        VALUES (:listing_id, 'Speciality', :value)
                    """), {"listing_id": listing_id, "value": speciality})

            count_local += 1

        # 2. Insert into Supabase cloud listings
        if cloud_db:
            try:
                check_cloud = cloud_db.execute(
                    text("SELECT id FROM listings WHERE name = :name AND phone = :phone"),
                    {"name": listing_dict["name"], "phone": listing_dict["phone"]}
                ).fetchone()

                if not check_cloud:
                    res_cloud = cloud_db.execute(text("""
                        INSERT INTO listings (name, address, phone, whatsapp, jd_url, category, subcategory, normalized_category, opening_hours, district, place, state, scraped_at)
                        VALUES (:name, :address, :phone, :whatsapp, :jd_url, :category, :subcategory, :normalized_category, :opening_hours, :district, :place, :state, :scraped_at)
                        RETURNING id
                    """), listing_dict)
                    cloud_listing_id = res_cloud.fetchone()[0]

                    if cloud_listing_id:
                        if profile_pic:
                            cloud_db.execute(text("""
                                INSERT INTO listing_images (listing_id, image_path, category, is_primary)
                                VALUES (:listing_id, :image_path, 'doctor_photo', true)
                            """), {"listing_id": cloud_listing_id, "image_path": profile_pic})

                        if qualification:
                            cloud_db.execute(text("""
                                INSERT INTO amenities (listing_id, category, value)
                                VALUES (:listing_id, 'Qualification', :value)
                            """), {"listing_id": cloud_listing_id, "value": qualification})

                        if speciality:
                            cloud_db.execute(text("""
                                INSERT INTO amenities (listing_id, category, value)
                                VALUES (:listing_id, 'Speciality', :value)
                            """), {"listing_id": cloud_listing_id, "value": speciality})

                    count_cloud += 1
            except Exception as e:
                pass

        if idx % 200 == 0 or idx == len(data):
            local_db.commit()
            if cloud_db:
                try:
                    cloud_db.commit()
                except Exception:
                    cloud_db.rollback()
            print(f"Uploaded {idx}/{len(data)} doctor listings...")

    local_db.close()
    if cloud_db:
        cloud_db.close()

    print("\n" + "=" * 60)
    print(f"  FINISHED UPLOADING DOCTORS TO MAIN WEB DASHBOARD!  ")
    print(f"Local Listings Inserted : {count_local}")
    if cloud_db:
        print(f"Supabase Web Listings Inserted : {count_cloud}")
    print("=" * 60)

if __name__ == "__main__":
    main()
