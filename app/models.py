from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Listing(Base):
    __tablename__ = "listings"
    
    id = Column(Integer, primary_key=True, index=True)
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
    
    images = relationship("ListingImage", back_populates="listing", cascade="all, delete-orphan")
    menu_items = relationship("MenuItem", back_populates="listing", cascade="all, delete-orphan")
    amenities = relationship("Amenity", back_populates="listing", cascade="all, delete-orphan")

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