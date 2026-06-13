from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
import json
import time

from app.database import get_db
from app import models

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])

@router.get("/fetch-from-justdial")
def fetch_justdial_categories(city: str = "Mumbai", db: Session = Depends(get_db)):
    """
    Fetch all categories from JustDial homepage and save to database
    """
    try:
        # Clear old categories
        db.query(models.Category).delete()
        db.commit()
        
        # Fetch JustDial homepage
        url = f"https://www.justdial.com/{city}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        categories_added = 0
        
        # Look for category sections in the page
        # JustDial structures categories in various ways
        category_sections = soup.find_all(['div', 'section'], class_=lambda x: x and ('category' in x.lower() or 'popular' in x.lower()))
        
        for section in category_sections:
            links = section.find_all('a', href=True)
            for link in links:
                category_name = link.get_text(strip=True)
                category_url = link.get('href', '')
                
                if category_name and len(category_name) > 2 and category_url:
                    # Determine parent category from context
                    parent = "General"
                    if 'food' in category_name.lower() or 'restaurant' in category_url.lower():
                        parent = "Food & Restaurants"
                    elif 'hotel' in category_name.lower() or 'accommodation' in category_url.lower():
                        parent = "Accommodation"
                    elif 'doctor' in category_name.lower() or 'hospital' in category_url.lower():
                        parent = "Health & Medical"
                    elif 'school' in category_name.lower() or 'education' in category_url.lower():
                        parent = "Education"
                    
                    # Check if category already exists
                    existing = db.query(models.Category).filter(
                        models.Category.name == category_name
                    ).first()
                    
                    if not existing:
                        new_category = models.Category(
                            name=category_name,
                            parent_category=parent,
                            sub_category=None,
                            jd_url=category_url if category_url.startswith('http') else f"https://www.justdial.com{category_url}",
                            is_active=True
                        )
                        db.add(new_category)
                        categories_added += 1
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Fetched {categories_added} categories from JustDial",
            "total_categories": db.query(models.Category).count()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")

@router.get("/list")
def list_categories(
    parent: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all categories with optional filtering
    """
    query = db.query(models.Category).filter(models.Category.is_active == True)
    
    if parent:
        query = query.filter(models.Category.parent_category == parent)
    
    if search:
        query = query.filter(models.Category.name.ilike(f"%{search}%"))
    
    categories = query.order_by(models.Category.parent_category, models.Category.name).all()
    
    return {
        "total": len(categories),
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "parent": c.parent_category,
                "url": c.jd_url
            }
            for c in categories
        ]
    }

@router.post("/select")
def select_category_for_scraping(
    category_id: int,
    city: str,
    db: Session = Depends(get_db)
):
    """
    Select a category for scraping in a specific city
    """
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Check if already selected
    existing = db.query(models.SelectedCategory).filter(
        models.SelectedCategory.category_id == category_id,
        models.SelectedCategory.city == city
    ).first()
    
    if existing:
        return {"status": "already_selected", "message": "Category already selected for this city"}
    
    selection = models.SelectedCategory(
        category_id=category_id,
        city=city
    )
    db.add(selection)
    db.commit()
    
    return {"status": "success", "message": f"Selected {category.name} for scraping in {city}"}

@router.get("/selected")
def get_selected_categories(city: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get all selected categories for scraping
    """
    query = db.query(models.SelectedCategory).join(models.Category)
    
    if city:
        query = query.filter(models.SelectedCategory.city == city)
    
    selections = query.all()
    
    return {
        "total": len(selections),
        "selections": [
            {
                "id": s.id,
                "category": s.category.name,
                "parent": s.category.parent_category,
                "city": s.city,
                "url": s.category.jd_url,
                "selected_at": s.selected_at.isoformat()
            }
            for s in selections
        ]
    }

@router.delete("/selected/{selection_id}")
def deselect_category(selection_id: int, db: Session = Depends(get_db)):
    """
    Remove a category from selected list
    """
    selection = db.query(models.SelectedCategory).filter(
        models.SelectedCategory.id == selection_id
    ).first()
    
    if not selection:
        raise HTTPException(status_code=404, detail="Selection not found")
    
    db.delete(selection)
    db.commit()
    
    return {"status": "success", "message": "Category deselected"}