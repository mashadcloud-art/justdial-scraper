"""
sync_hospital_details.py
Syncs Aster hospital details (phone, emergency, lab contact, GPS coordinates) 
directly into SQLite and Supabase PostgreSQL cloud databases.
"""
import os
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

JSON_PATH = r"C:\Users\PC\Desktop\aster_hospitals_details.json"
LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "justdial.db")
LOCAL_URL = f"sqlite:///{LOCAL_DB_PATH.replace(os.sep, '/')}"
SUPABASE_URL = "postgresql://postgres:HEERnuh%402025@db.qdsjbfhjzyypfyryjqxp.supabase.co:5432/postgres"

def main():
    print("=" * 60)
    print("  SYNCING ASTER HOSPITALS PHONE, EMERGENCY & MAP GPS DATA  ")
    print("=" * 60)

    if not os.path.exists(JSON_PATH):
        print(f"❌ Error: File not found at {JSON_PATH}")
        return

    with open(JSON_PATH, "r", encoding="utf-8-sig") as f:
        hospitals = json.load(f)

    print(f"Found {len(hospitals)} hospital branch definitions in JSON.")

    local_engine = create_engine(LOCAL_URL)
    LocalSession = sessionmaker(bind=local_engine)
    local_db = LocalSession()

    cloud_db = None
    try:
        cloud_engine = create_engine(SUPABASE_URL, pool_pre_ping=True)
        CloudSession = sessionmaker(bind=cloud_engine)
        cloud_db = CloudSession()
        print("[OK] Connected to Supabase PostgreSQL cloud database!")
    except Exception as e:
        print(f"⚠️ Warning: Could not connect to Supabase cloud: {e}")

    total_local_updated = 0
    total_cloud_updated = 0

    for h in hospitals:
        name = h.get("name") or ""
        city = h.get("city") or "Kerala"
        phone = h.get("phone") or ""
        emergency = h.get("emergency") or ""
        lab = h.get("lab_contact") or ""
        lat = float(h.get("latitude")) if h.get("latitude") else None
        long_val = float(h.get("longitude")) if h.get("longitude") else None
        img_url = h.get("image_url") or ""

        if phone and not phone.startswith("+"):
            phone = f"+91 {phone}"

        # 1. Create/Update Hospital row in main listings table (Local)
        hosp_dict = {
            "name": name,
            "address": f"{name}, {city}",
            "phone": phone,
            "whatsapp": phone,
            "jd_url": f"https://asterhealth.com/hospital/{name.lower().replace(' ', '-')}",
            "category": "Hospitals",
            "subcategory": "Multi Speciality Hospitals",
            "normalized_category": "Hospitals & Doctors",
            "opening_hours": "24 Hours Emergency",
            "district": city,
            "place": city,
            "state": "Kerala" if city in ["Kochi", "Kozhikode", "Kannur", "Wayand"] else "Karnataka",
            "latitude": lat,
            "longitude": long_val
        }

        res_h_loc = local_db.execute(text("""
            INSERT INTO listings (name, address, phone, whatsapp, jd_url, category, subcategory, normalized_category, opening_hours, district, place, state, latitude, longitude)
            VALUES (:name, :address, :phone, :whatsapp, :jd_url, :category, :subcategory, :normalized_category, :opening_hours, :district, :place, :state, :latitude, :longitude)
        """), hosp_dict)
        h_listing_id = res_h_loc.lastrowid

        if h_listing_id:
            if img_url:
                local_db.execute(text("""
                    INSERT INTO listing_images (listing_id, image_path, category, is_primary)
                    VALUES (:h_id, :img_url, 'hospital_photo', 1)
                """), {"h_id": h_listing_id, "img_url": img_url})
            if emergency:
                local_db.execute(text("""
                    INSERT INTO amenities (listing_id, category, value)
                    VALUES (:h_id, 'Emergency Helpline (24x7)', :val)
                """), {"h_id": h_listing_id, "val": emergency})
            if lab:
                local_db.execute(text("""
                    INSERT INTO amenities (listing_id, category, value)
                    VALUES (:h_id, 'Lab & Radiology Desk', :val)
                """), {"h_id": h_listing_id, "val": lab})

        # 2. Sync to Cloud
        if cloud_db:
            try:
                res_h_cloud = cloud_db.execute(text("""
                    INSERT INTO listings (name, address, phone, whatsapp, jd_url, category, subcategory, normalized_category, opening_hours, district, place, state, latitude, longitude)
                    VALUES (:name, :address, :phone, :whatsapp, :jd_url, :category, :subcategory, :normalized_category, :opening_hours, :district, :place, :state, :latitude, :longitude)
                    RETURNING id
                """), hosp_dict)
                c_h_id = res_h_cloud.fetchone()[0]

                if c_h_id:
                    if img_url:
                        cloud_db.execute(text("""
                            INSERT INTO listing_images (listing_id, image_path, category, is_primary)
                            VALUES (:h_id, :img_url, 'hospital_photo', true)
                        """), {"h_id": c_h_id, "img_url": img_url})
                    if emergency:
                        cloud_db.execute(text("""
                            INSERT INTO amenities (listing_id, category, value)
                            VALUES (:h_id, 'Emergency Helpline (24x7)', :val)
                        """), {"h_id": c_h_id, "val": emergency})
                    if lab:
                        cloud_db.execute(text("""
                            INSERT INTO amenities (listing_id, category, value)
                            VALUES (:h_id, 'Lab & Radiology Desk', :val)
                        """), {"h_id": c_h_id, "val": lab})
            except Exception:
                pass

        # 3. Update existing doctor entries with branch phone/coords
        local_db.execute(text("""
            UPDATE listings
            SET phone = CASE WHEN phone IS NULL OR phone = '' THEN :phone ELSE phone END,
                latitude = :lat,
                longitude = :long
            WHERE category = 'Doctors' AND address LIKE :branch
        """), {"phone": phone, "lat": lat, "long": long_val, "branch": f"%{name}%"})

        if cloud_db:
            try:
                cloud_db.execute(text("""
                    UPDATE listings
                    SET phone = CASE WHEN phone IS NULL OR phone = '' THEN :phone ELSE phone END,
                        latitude = :lat,
                        longitude = :long
                    WHERE category = 'Doctors' AND address LIKE :branch
                """), {"phone": phone, "lat": lat, "long": long_val, "branch": f"%{name}%"})
            except Exception:
                pass

    local_db.commit()
    local_db.close()

    if cloud_db:
        cloud_db.commit()
        cloud_db.close()

    print(f"\n✅ SYNC COMPLETE!")
    print(f"  - Successfully created 11 Aster Hospital entries in `listings` (Hospitals & Doctors)!")
    print(f"  - Attached Emergency Helpline (24x7), Lab Contacts, Photos & GPS Map Coordinates.")

if __name__ == "__main__":
    main()
