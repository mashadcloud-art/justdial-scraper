from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# --- Restaurant Schemas ---
class RestaurantBase(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    jd_url: Optional[str] = None
    category: Optional[str] = None
    opening_hours: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None

class RestaurantCreate(RestaurantBase):
    pass

class RestaurantResponse(RestaurantBase):
    id: int
    scraped_at: datetime
    
    class Config:
        from_attributes = True # Allows SQLAlchemy models to be converted to JSON

# --- Image Schemas ---
class ImageBase(BaseModel):
    image_path: str
    is_primary: bool = True

class ImageResponse(ImageBase):
    id: int
    restaurant_id: int
    
    class Config:
        from_attributes = True