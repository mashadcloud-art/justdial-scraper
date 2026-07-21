from sqlalchemy import Column, Integer, BigInteger, Float, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Listing(Base):
    __tablename__ = "listings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=True, index=True)
    name = Column(String(500), nullable=False, index=True)
    address = Column(Text)
    phone = Column(String(50))
    whatsapp = Column(String(50))
    jd_url = Column(String(500))
    category = Column(String(200))
    subcategory = Column(String(200), nullable=True)
    normalized_category = Column(String(100), nullable=True, index=True)  # Parent group: "Beauty & Spas", "Hotels & Restaurants", etc.
    opening_hours = Column(String(200))
    district = Column(String(100), nullable=True)
    place = Column(String(200), nullable=True)   # locality within district (e.g. Kuttikkanam)
    state = Column(String(100), nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)
    school_code = Column(BigInteger, nullable=True, index=True)  # Links to schools.school_code after merge
    
    images = relationship("ListingImage", back_populates="listing", cascade="all, delete-orphan")
    menu_items = relationship("MenuItem", back_populates="listing", cascade="all, delete-orphan")
    amenities = relationship("Amenity", back_populates="listing", cascade="all, delete-orphan")
    professionals = relationship("Professional", back_populates="listing", cascade="all, delete-orphan")

class ListingImage(Base):
    __tablename__ = "listing_images"
    
    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    image_path = Column(String(500))
    category = Column(String(50), default="general")
    is_primary = Column(Boolean, default=False)
    
    listing = relationship("Listing", back_populates="images")

class MenuItem(Base):
    __tablename__ = "menu_items"
    
    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    name = Column(String(200))
    price = Column(String(50))
    is_veg = Column(Boolean, default=True)
    
    listing = relationship("Listing", back_populates="menu_items")

class Amenity(Base):
    __tablename__ = "amenities"
    
    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    category = Column(String(100))
    value = Column(String(200))
    
    listing = relationship("Listing", back_populates="amenities")

# ==========================================
# NEW: CATEGORY MODELS
# ==========================================
class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    parent_category = Column(String(200), nullable=True)
    sub_category = Column(String(200), nullable=True)
    jd_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SelectedCategory(Base):
    __tablename__ = "selected_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    city = Column(String(100))
    selected_at = Column(DateTime, default=datetime.utcnow)
    category = relationship("Category", backref="selections")

# ==========================================
# NEW: KERALA SCHOOLS MODELS (Supabase Schema)
# ==========================================
class School(Base):
    __tablename__ = "schools"
    
    school_code = Column(BigInteger, primary_key=True)
    udise_code = Column(BigInteger, nullable=True)
    hss_code = Column(Text, nullable=True)
    vhse_code = Column(Text, nullable=True)
    name = Column(Text, nullable=False)
    type = Column(Text, nullable=True)
    level = Column(Text, nullable=True)
    established_year = Column(Integer, nullable=True)
    address = Column(Text, nullable=True)
    pin_code = Column(Integer, nullable=True)
    district = Column(Text, nullable=True, index=True)
    sub_district = Column(Text, nullable=True)
    education_district = Column(Text, nullable=True)
    assembly_constituency = Column(Text, nullable=True)
    parliament_constituency = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_coastal_area = Column(Boolean, nullable=True)
    is_hilly_area = Column(Boolean, nullable=True)
    principal_name = Column(Text, nullable=True)
    head_master_name = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    hse_start_year = Column(Integer, nullable=True)
    
    contacts = relationship("SchoolContact", back_populates="school", cascade="all, delete-orphan")
    facilities = relationship("SchoolFacility", back_populates="school", uselist=False, cascade="all, delete-orphan")
    staff_positions = relationship("SchoolStaffPosition", back_populates="school", cascade="all, delete-orphan")


class SchoolContact(Base):
    __tablename__ = "school_contacts"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    school_code = Column(BigInteger, ForeignKey("schools.school_code", ondelete="CASCADE"), nullable=False, index=True)
    section = Column(Text, nullable=True)
    email = Column(Text, nullable=True)
    phone = Column(Text, nullable=True)
    
    school = relationship("School", back_populates="contacts")


class SchoolFacility(Base):
    __tablename__ = "school_facilities"
    
    school_code = Column(BigInteger, ForeignKey("schools.school_code", ondelete="CASCADE"), primary_key=True)
    total_area_acre = Column(Text, nullable=True)
    survey_number_s = Column(Text, nullable=True)
    land_obtained_for_establishing_school = Column(Text, nullable=True)
    land_protected_by = Column(Text, nullable=True)
    building_type = Column(Text, nullable=True)
    building_plinth_area = Column(Text, nullable=True)
    building_ownership = Column(Text, nullable=True)
    library = Column(Text, nullable=True)
    electrification = Column(Text, nullable=True)
    solar_power = Column(Text, nullable=True)
    drinking_water = Column(Text, nullable=True)
    net_connectivity = Column(Text, nullable=True)
    total_class_room = Column(Integer, nullable=True)
    multi_media_room = Column(Text, nullable=True)
    total_smart_class_room = Column(Integer, nullable=True)
    little_kites = Column(Text, nullable=True)
    total_staff_room = Column(Integer, nullable=True)
    computer_lab = Column(Text, nullable=True)
    science_lab = Column(Text, nullable=True)
    total_no_of_computers_available_in_the_school = Column(Integer, nullable=True)
    total_no_of_printers_available_in_the_school = Column(Integer, nullable=True)
    first_aid_room = Column(Text, nullable=True)
    public_addressing_system = Column(Text, nullable=True)
    kitchen = Column(Text, nullable=True)
    cctv = Column(Text, nullable=True)
    store_book_stationary = Column(Text, nullable=True)
    tv_hall = Column(Text, nullable=True)
    canteen = Column(Text, nullable=True)
    rainwater_harvesting = Column(Text, nullable=True)
    play_ground = Column(Text, nullable=True)
    waste_management_system = Column(Text, nullable=True)
    autism_park = Column(Text, nullable=True)
    dining_hall = Column(Text, nullable=True)
    auditorium = Column(Text, nullable=True)
    indoor_stadium = Column(Text, nullable=True)
    students_police = Column(Text, nullable=True)
    music_class_room = Column(Text, nullable=True)
    activities = Column(Text, nullable=True)
    agricultural_activity = Column(Text, nullable=True)
    toilet = Column(Text, nullable=True)
    she_toilet = Column(Text, nullable=True)
    no_of_toilets_for_boys = Column(Integer, nullable=True)
    no_of_toilets_for_girls = Column(Integer, nullable=True)
    no_of_urinals_for_boys = Column(Integer, nullable=True)
    no_of_urinals_for_girls = Column(Integer, nullable=True)
    parking_space = Column(Text, nullable=True)
    garden = Column(Text, nullable=True)
    transportation = Column(Text, nullable=True)
    hostel_facility = Column(Text, nullable=True)
    bio_gas = Column(Text, nullable=True)
    incinerator_facility = Column(Text, nullable=True)
    
    school = relationship("School", back_populates="facilities")


class SchoolStaffPosition(Base):
    __tablename__ = "school_staff_positions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    school_code = Column(BigInteger, ForeignKey("schools.school_code", ondelete="CASCADE"), nullable=False, index=True)
    position_title = Column(Text, nullable=False, index=True)
    sanctioned_posts = Column(Integer, nullable=False, default=1)
    
    school = relationship("School", back_populates="staff_positions")


class ModuleConfig(Base):
    __tablename__ = "module_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(String(100), unique=True, index=True)
    is_enabled = Column(Boolean, default=False)
    settings = Column(Text, nullable=True)  # JSON stored as text
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ScraperJob(Base):
    __tablename__ = "scraper_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=True, index=True)
    district = Column(String(100), nullable=False)
    query = Column(String(200), nullable=False)
    category = Column(String(200), nullable=False)
    normalized_category = Column(String(100), nullable=False)
    max_photos = Column(Integer, default=1)
    status = Column(String(50), default="pending") # pending, running, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class CourseProvider(Base):
    __tablename__ = "course_providers"
    
    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Professional(Base):
    __tablename__ = "professionals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    image_url = Column(Text)
    achievement = Column(Text)
    tags = Column(String(500))
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="professionals")

# ==========================================
# NEW: DEEP CATEGORY SCRAPER MODELS
# ==========================================
class JDCategory(Base):
    __tablename__ = "jd_categories"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(100), nullable=False, index=True)
    parent_category = Column(String(200), nullable=False)
    subcategory_name = Column(String(200), nullable=False)
    subcategory_nct_code = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeepScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(50), unique=True, index=True, nullable=False)
    url = Column(String(1000), nullable=False)
    mode = Column(String(20), nullable=False)  # "district" or "state"
    status = Column(String(30), default="pending")  # pending, discovering, scraping, completed, failed, stopped
    control = Column(String(20), default="run")  # run, pause, stop — checked by the worker thread between subcategories
    total_subcategories = Column(Integer, default=0)
    completed_subcategories = Column(Integer, default=0)
    total_found = Column(Integer, default=0)
    duplicates_skipped = Column(Integer, default=0)
    current_subcategory = Column(String(300), nullable=True)
    log_tail = Column(Text, nullable=True)  # JSON-encoded list of recent log lines, for the live log panel
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JDCategoryMap(Base):
    """Persistent subcategory map for the Deep Category Scraper — seeded with defaults, extendable
    by pasting a JustDial category page's HTML. city=NULL rows are global defaults applied to every
    city; city-scoped rows come from HTML pasted for that city's page specifically."""
    __tablename__ = "jd_category_map"

    id = Column(Integer, primary_key=True, index=True)
    main_category = Column(String(200), nullable=False, index=True)
    subcategory = Column(String(200), nullable=False)
    tags = Column(String(300), nullable=True)
    city = Column(String(100), nullable=True, index=True)
    resolved_name = Column(String(200), nullable=True)  # canonical category name JD's search index actually recognizes, from a live redirect resolution (see resolve_category())
    created_at = Column(DateTime, default=datetime.utcnow)


# ==========================================
# NEW: ASTER HOSPITALS SCRAPER
# ==========================================
class AsterHospital(Base):
    __tablename__ = "aster_hospitals"

    id = Column(Integer, primary_key=True, index=True)
    aster_id = Column(Integer, unique=True, index=True, nullable=False)  # numeric id from the given slug-id (e.g. 1300)
    slug = Column(String(200), nullable=False)  # doctors-listing slug, e.g. aster-mims-kannur
    detail_slug = Column(String(200), nullable=True)  # /hospitals/{slug} slug — sometimes differs from the doctors-listing slug
    name = Column(String(300), nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String(100), nullable=True)
    helpline = Column(String(300), nullable=True)
    email = Column(String(200), nullable=True)
    specialities = Column(Text, nullable=True)  # comma-joined
    facilities = Column(Text, nullable=True)  # comma-joined, best-effort (site has no dedicated facilities section on every page)
    about = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    map_link = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending, scraped, failed
    doctors_status = Column(String(20), default="pending")  # pending, scraped, failed
    doctor_count = Column(Integer, default=0)
    error_detail = Column(Text, nullable=True)
    scraped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AsterDoctor(Base):
    __tablename__ = "aster_doctors"

    id = Column(Integer, primary_key=True, index=True)
    hospital_aster_id = Column(Integer, ForeignKey("aster_hospitals.aster_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(300), nullable=False)
    detail_url = Column(Text, nullable=False, unique=True)  # dedup key
    designation = Column(String(300), nullable=True)
    qualifications = Column(String(500), nullable=True)
    speciality = Column(String(300), nullable=True)
    hospital_name_raw = Column(String(300), nullable=True)  # hospital name exactly as shown on the doctor card, for QA
    bio_snippet = Column(Text, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)