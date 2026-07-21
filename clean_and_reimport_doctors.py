"""
clean_and_reimport_doctors.py
Clears doctor listings from listings/amenities and re-imports them cleanly with separate Name, Qualification, and Speciality attributes.
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
    print("  RE-IMPORTING DOCTORS WITH SEPARATED QUALIFICATION & SPECIALITY  ")
    print("=" * 60)

    with open(JSON_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)
    local_engine = create_engine(LOCAL_URL)
    from app.models import Base
    Base.metadata.create_all(bind=local_engine)
    LocalSession = sessionmaker(bind=local_engine)
    local_db = LocalSession()

    cloud_db = None
    try:
        cloud_engine = create_engine(SUPABASE_URL, pool_pre_ping=True)
        Base.metadata.create_all(bind=cloud_engine)
        CloudSession = sessionmaker(bind=cloud_engine)
        cloud_db = CloudSession()
    except Exception as e:
        print(f"Warning connecting to cloud: {e}")

    # Delete existing doctor category listings from listings to clean up
    print("Cleaning old doctor listings...")
    try:
        local_db.execute(text("DELETE FROM listing_images WHERE listing_id IN (SELECT id FROM listings WHERE category = 'Doctors')"))
        local_db.execute(text("DELETE FROM amenities WHERE listing_id IN (SELECT id FROM listings WHERE category = 'Doctors')"))
        local_db.execute(text("DELETE FROM listings WHERE category = 'Doctors'"))
        local_db.commit()
    except Exception as e:
        local_db.rollback()

    if cloud_db:
        try:
            cloud_db.execute(text("DELETE FROM listing_images WHERE listing_id IN (SELECT id FROM listings WHERE category = 'Doctors')"))
            cloud_db.execute(text("DELETE FROM amenities WHERE listing_id IN (SELECT id FROM listings WHERE category = 'Doctors')"))
            cloud_db.execute(text("DELETE FROM listings WHERE category = 'Doctors'"))
            cloud_db.commit()
        except Exception as e:
            cloud_db.rollback()

    # Load hospital details map for enrichments
    hosp_map = {}
    hosp_details_path = r"C:\Users\PC\Desktop\aster_hospitals_details_hd.json"
    if not os.path.exists(hosp_details_path):
        hosp_details_path = r"C:\Users\PC\Desktop\aster_hospitals_details.json"

    if os.path.exists(hosp_details_path):
        try:
            with open(hosp_details_path, "r", encoding="utf-8-sig") as hf:
                h_list = json.load(hf)
                for h in h_list:
                    hosp_map[h.get("name", "").strip().lower()] = h
        except Exception:
            pass

    print("Re-inserting doctor profiles with complete Hospital Emergency, Lab & Map GPS Data...")
    count = 0
    for idx, item in enumerate(data, 1):
        user_info = item.get("user") or {}
        doc_name = item.get("name") or f"Dr. {user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
        
        raw_qual = item.get("qualification")
        qualification = str(raw_qual).strip() if raw_qual else ""

        branches_list = item.get("branches") or []
        branch_name = branches_list[0] if branches_list else "Aster Hospital"

        # Lookup hospital details for branch
        h_info = hosp_map.get(branch_name.strip().lower(), {})
        
        h_phone = h_info.get("phone") or ""
        h_emergency = h_info.get("emergency") or ""
        h_lab = h_info.get("lab_contact") or ""
        h_lat = float(h_info.get("latitude")) if h_info.get("latitude") else None
        h_long = float(h_info.get("longitude")) if h_info.get("longitude") else None

        phone = user_info.get("phone") or h_phone
        if phone and not phone.startswith("+"):
            phone = f"+91 {phone}"

        branches_info = item.get("branches_info") or []
        cities = list(set(b.get("city") for b in branches_info if b.get("city")))
        district = h_info.get("city") or (cities[0] if cities else "Kerala")

        specialities_list = item.get("specialities") or []
        speciality = specialities_list[0] if specialities_list else "Doctors"

        address = f"{branch_name}, {district}"
        profile_pic = item.get("profile_pic") or item.get("external_profile_pic") or ""

        listing_dict = {
            "name": doc_name,
            "address": address,
            "phone": phone,
            "whatsapp": phone,
            "jd_url": f"https://asterhealth.com/doctor/{item.get('id')}",
            "category": "Doctors",
            "subcategory": speciality,
            "normalized_category": "Hospitals & Doctors",
            "opening_hours": "09:00 AM - 05:00 PM",
            "district": district,
            "place": district,
            "state": "Kerala" if district in ["Kozhikode", "Kochi", "Kannur", "Malappuram", "Thiruvananthapuram", "Wayand", "Palakkad", "Areekode"] else "Karnataka",
            "latitude": h_lat,
            "longitude": h_long,
            "scraped_at": datetime.utcnow()
        }

        # Local
        res = local_db.execute(text("""
            INSERT INTO listings (name, address, phone, whatsapp, jd_url, category, subcategory, normalized_category, opening_hours, district, place, state, latitude, longitude, scraped_at)
            VALUES (:name, :address, :phone, :whatsapp, :jd_url, :category, :subcategory, :normalized_category, :opening_hours, :district, :place, :state, :latitude, :longitude, :scraped_at)
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
                    VALUES (:listing_id, 'Speciality / Area of Expertise', :value)
                """), {"listing_id": listing_id, "value": speciality})

            exp = item.get("experience") or item.get("exp")
            if exp:
                local_db.execute(text("""
                    INSERT INTO amenities (listing_id, category, value)
                    VALUES (:listing_id, 'Experience', :value)
                """), {"listing_id": listing_id, "value": f"{exp} Years of Experience"})

            designation = item.get("designation")
            if designation:
                local_db.execute(text("""
                    INSERT INTO amenities (listing_id, category, value)
                    VALUES (:listing_id, 'Designation', :value)
                """), {"listing_id": listing_id, "value": str(designation).capitalize()})

            languages = item.get("language")
            if languages:
                local_db.execute(text("""
                    INSERT INTO amenities (listing_id, category, value)
                    VALUES (:listing_id, 'Languages Spoken', :value)
                """), {"listing_id": listing_id, "value": languages})

            fee_range = item.get("fee_range")
            if fee_range:
                local_db.execute(text("""
                    INSERT INTO amenities (listing_id, category, value)
                    VALUES (:listing_id, 'Consultation Fee', :value)
                """), {"listing_id": listing_id, "value": f"₹{fee_range}"})

            if h_emergency:
                local_db.execute(text("""
                    INSERT INTO amenities (listing_id, category, value)
                    VALUES (:listing_id, 'Hospital Emergency (24x7)', :value)
                """), {"listing_id": listing_id, "value": h_emergency})

            if h_lab:
                local_db.execute(text("""
                    INSERT INTO amenities (listing_id, category, value)
                    VALUES (:listing_id, 'Hospital Lab Contact', :value)
                """), {"listing_id": listing_id, "value": h_lab})

        # Cloud
        if cloud_db:
            try:
                res_cloud = cloud_db.execute(text("""
                    INSERT INTO listings (name, address, phone, whatsapp, jd_url, category, subcategory, normalized_category, opening_hours, district, place, state, latitude, longitude, scraped_at)
                    VALUES (:name, :address, :phone, :whatsapp, :jd_url, :category, :subcategory, :normalized_category, :opening_hours, :district, :place, :state, :latitude, :longitude, :scraped_at)
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
                            VALUES (:listing_id, 'Speciality / Area of Expertise', :value)
                        """), {"listing_id": cloud_listing_id, "value": speciality})

                    exp = item.get("experience") or item.get("exp")
                    if exp:
                        cloud_db.execute(text("""
                            INSERT INTO amenities (listing_id, category, value)
                            VALUES (:listing_id, 'Experience', :value)
                        """), {"listing_id": cloud_listing_id, "value": f"{exp} Years of Experience"})

                    designation = item.get("designation")
                    if designation:
                        cloud_db.execute(text("""
                            INSERT INTO amenities (listing_id, category, value)
                            VALUES (:listing_id, 'Designation', :value)
                        """), {"listing_id": cloud_listing_id, "value": str(designation).capitalize()})

                    languages = item.get("language")
                    if languages:
                        cloud_db.execute(text("""
                            INSERT INTO amenities (listing_id, category, value)
                            VALUES (:listing_id, 'Languages Spoken', :value)
                        """), {"listing_id": cloud_listing_id, "value": languages})

                    fee_range = item.get("fee_range")
                    if fee_range:
                        cloud_db.execute(text("""
                            INSERT INTO amenities (listing_id, category, value)
                            VALUES (:listing_id, 'Consultation Fee', :value)
                        """), {"listing_id": cloud_listing_id, "value": f"₹{fee_range}"})

                    if h_emergency:
                        cloud_db.execute(text("""
                            INSERT INTO amenities (listing_id, category, value)
                            VALUES (:listing_id, 'Hospital Emergency (24x7)', :value)
                        """), {"listing_id": cloud_listing_id, "value": h_emergency})

                    if h_lab:
                        cloud_db.execute(text("""
                            INSERT INTO amenities (listing_id, category, value)
                            VALUES (:listing_id, 'Hospital Lab Contact', :value)
                        """), {"listing_id": cloud_listing_id, "value": h_lab})
            except Exception as e:
                pass

        count += 1
        if idx % 300 == 0 or idx == len(data):
            local_db.commit()
            if cloud_db:
                try:
                    cloud_db.commit()
                except Exception:
                    cloud_db.rollback()
            print(f"Cleanly re-imported {idx}/{len(data)} doctors...")

    local_db.close()
    if cloud_db:
        cloud_db.close()
    print(f"\n✅ RE-IMPORT COMPLETE! Cleaned and updated {count} doctor profiles.")

if __name__ == "__main__":
    main()
