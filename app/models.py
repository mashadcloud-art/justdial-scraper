from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Restaurant(Base):
    __tablename__ = "restaurants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False, index=True)
    address = Column(Text)
    phone = Column(String(50))
    whatsapp = Column(String(50))
    jd_url = Column(String(500))
    category = Column(String(200))
    subcategory = Column(String(200), nullable=True)
    opening_hours = Column(String(200))
    district = Column(String(100), nullable=True)
    place = Column(String(200), nullable=True)   # locality within district (e.g. Kuttikkanam)
    state = Column(String(100), nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)
    
    images = relationship("RestaurantImage", back_populates="restaurant", cascade="all, delete-orphan")
    menu_items = relationship("MenuItem", back_populates="restaurant", cascade="all, delete-orphan")
    amenities = relationship("Amenity", back_populates="restaurant", cascade="all, delete-orphan")

class RestaurantImage(Base):
    __tablename__ = "restaurant_images"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    image_path = Column(String(500))
    category = Column(String(50), default="general")
    is_primary = Column(Boolean, default=False)
    
    restaurant = relationship("Restaurant", back_populates="images")

class MenuItem(Base):
    __tablename__ = "menu_items"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    name = Column(String(200))
    price = Column(String(50))
    is_veg = Column(Boolean, default=True)
    
    restaurant = relationship("Restaurant", back_populates="menu_items")

class Amenity(Base):
    __tablename__ = "amenities"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    category = Column(String(100))
    value = Column(String(200))
    
    restaurant = relationship("Restaurant", back_populates="amenities")

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