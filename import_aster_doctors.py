"""
import_aster_doctors.py
Uploads doctors from aster_merged.json on the Desktop to both local SQLite database and Supabase cloud database.
"""

import os
import json
from datetime import datetime
from sqlalchemy import create_engine, text, Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

# Path to the aster_merged.json on Desktop
JSON_PATH = r"C:\Users\PC\Desktop\aster_merged.json"

# Local SQLite Database
LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "justdial.db")
LOCAL_URL = f"sqlite:///{LOCAL_DB_PATH.replace(os.sep, '/')}"

# Supabase Postgres Database
SUPABASE_URL = "postgresql://postgres:HEERnuh%402025@db.qdsjbfhjzyypfyryjqxp.supabase.co:5432/postgres"

Base = declarative_base()

class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    aster_uuid = Column(String(100), unique=True, index=True, nullable=False)
    reg_no = Column(String(100), nullable=True)
    name = Column(String(300), nullable=False, index=True)
    qualification = Column(Text, nullable=True)
    practicing_since = Column(Integer, nullable=True)
    experience_years = Column(Integer, nullable=True)
    languages = Column(String(300), nullable=True)
    gender = Column(String(50), nullable=True)
    designation = Column(String(300), nullable=True)
    
    # Contact Details (from user object)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True, index=True)
    country_code = Column(String(20), nullable=True)
    
    # Hospital & Branch Details
    branches = Column(Text, nullable=True)         # comma-joined
    cities = Column(Text, nullable=True)           # comma-joined
    specialities = Column(Text, nullable=True)     # comma-joined
    fee_range = Column(String(100), nullable=True)
    
    # Profile Links & Status
    profile_pic = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def main():
    print("=" * 60)
    print("      IMPORTING ASTER DOCTORS TO LOCAL & CLOUD DATABASE      ")
    print("=" * 60)

    if not os.path.exists(JSON_PATH):
        print(f"❌ Error: File not found at {JSON_PATH}")
        return

    print(f"Reading {JSON_PATH}...")
    with open(JSON_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    print(f"Found {len(data)} total records to import.\n")

    # Connect Local
    print("Connecting to local SQLite database...")
    local_engine = create_engine(LOCAL_URL)
    Base.metadata.create_all(bind=local_engine)
    LocalSession = sessionmaker(bind=local_engine)
    local_db = LocalSession()

    # Connect Cloud
    cloud_db = None
    try:
        print("Connecting to Supabase Cloud database...")
        cloud_engine = create_engine(SUPABASE_URL, pool_pre_ping=True)
        Base.metadata.create_all(bind=cloud_engine)
        CloudSession = sessionmaker(bind=cloud_engine)
        cloud_db = CloudSession()
        print("Connected to Supabase successfully!")
    except Exception as e:
        print(f"⚠️ Warning: Could not connect to Supabase: {e}")

    # Process and prepare records
    imported_local = 0
    imported_cloud = 0
    updated_local = 0
    updated_cloud = 0

    for idx, item in enumerate(data, 1):
        aster_uuid = item.get("id")
        if not aster_uuid:
            continue

        user_info = item.get("user") or {}
        
        # Extract branches and cities
        branches_list = item.get("branches") or []
        branches_str = ", ".join(branches_list) if isinstance(branches_list, list) else str(branches_list)

        branches_info = item.get("branches_info") or []
        cities = list(set(b.get("city") for b in branches_info if b.get("city")))
        cities_str = ", ".join(cities)

        specialities_list = item.get("specialities") or []
        specialities_str = ", ".join(specialities_list) if isinstance(specialities_list, list) else str(specialities_list)

        doc_dict = {
            "aster_uuid": aster_uuid,
            "reg_no": item.get("reg_no"),
            "name": item.get("name") or f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip(),
            "qualification": item.get("qualification"),
            "practicing_since": item.get("practicing_since"),
            "experience_years": item.get("experience") or item.get("exp"),
            "languages": item.get("language"),
            "gender": item.get("gender"),
            "designation": item.get("designation"),
            "email": user_info.get("email"),
            "phone": user_info.get("phone"),
            "country_code": user_info.get("country_code"),
            "branches": branches_str,
            "cities": cities_str,
            "specialities": specialities_str,
            "fee_range": item.get("fee_range"),
            "profile_pic": item.get("profile_pic") or item.get("external_profile_pic"),
            "is_active": item.get("is_active", True)
        }

        # Insert/Update Local
        existing_local = local_db.query(Doctor).filter(Doctor.aster_uuid == aster_uuid).first()
        if existing_local:
            for k, v in doc_dict.items():
                setattr(existing_local, k, v)
            updated_local += 1
        else:
            local_db.add(Doctor(**doc_dict))
            imported_local += 1

        # Insert/Update Cloud
        if cloud_db:
            try:
                existing_cloud = cloud_db.query(Doctor).filter(Doctor.aster_uuid == aster_uuid).first()
                if existing_cloud:
                    for k, v in doc_dict.items():
                        setattr(existing_cloud, k, v)
                    updated_cloud += 1
                else:
                    cloud_db.add(Doctor(**doc_dict))
                    imported_cloud += 1
            except Exception as e:
                pass

        if idx % 500 == 0 or idx == len(data):
            local_db.commit()
            if cloud_db:
                try:
                    cloud_db.commit()
                except Exception:
                    cloud_db.rollback()
            print(f"Processed {idx}/{len(data)} doctor profiles...")

    local_db.close()
    if cloud_db:
        cloud_db.close()

    print("\n" + "=" * 60)
    print("  SUCCESSFULLY FINISHED DOCTOR IMPORT!  ")
    print(f"Local Database  : {imported_local} inserted, {updated_local} updated.")
    if cloud_db:
        print(f"Supabase Cloud  : {imported_cloud} inserted, {updated_cloud} updated.")
    print("=" * 60)

if __name__ == "__main__":
    main()
