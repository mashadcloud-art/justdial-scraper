import os
import json

# JustDial category data - CORRECT groupings!
JUSTDIAL_MAIN_CATEGORIES = {
    "Automobiles": {
        "subcategories": ["Car Dealers", "Car Repair & Services", "Second Hand Car Dealers", "Motorcycle Dealers", "Bike Repair & Services", "Car Accessories", "Car Rental", "Tyres & Tubeless", "Car Washing Services", "Driving Schools"]
    },
    "Banks & Financial Services": {
        "subcategories": ["Banks", "ATM", "Loans", "Personal Loans", "Home Loans", "Credit Cards", "Insurance Agents", "Mutual Funds", "Stock Brokers"]
    },
    "Beauty & Spas": {
        "subcategories": ["Beauty Parlours", "Beauty Spas", "Hair Stylists", "Makeup Artists", "Salons", "Skin Care Clinics", "Nail Spas", "Bridal Makeup"]
    },
    "Education": {
        "subcategories": ["Schools", "Colleges", "Tutorials", "Coaching Classes", "Computer Training Institutes", "Language Classes", "Play Schools", "MBA Colleges", "Engineering Colleges"]
    },
    "Electronics": {
        "subcategories": ["Mobile Phone Dealers", "Laptop Dealers", "Electronic Goods Showrooms", "TV Repair & Services", "AC Repair & Services", "Computer Repair & Services", "Mobile Phone Repair & Services"]
    },
    "Entertainment": {
        "subcategories": ["Cinema Halls", "Event Organisers", "DJs", "Bands", "Gaming Zones", "Amusement Parks", "Sports Clubs", "Dance Classes"]
    },
    "Health & Medical": {
        "subcategories": ["Hospitals", "Clinics", "Doctors", "Dentists", "Pathology Labs", "Medical Shops", "Ayurvedic Clinics", "Physiotherapists", "Eye Hospitals"]
    },
    "Home Services": {
        "subcategories": ["Packers & Movers", "Pest Control Services", "Electricians", "Plumbers", "Carpenters", "AC Repair & Services", "Refrigerator Repair", "Home Cleaning Services", "Painters", "Interior Designers"]
    },
    "Hotels & Restaurants": {
        "subcategories": ["Restaurants", "Hotels", "Fast Food", "Cafes", "Bakeries", "Ice Cream Parlours", "Lounge Bars", "Multicuisine Restaurants", "South Indian Restaurants", "North Indian Restaurants"]
    },
    "Legal & Professional Services": {
        "subcategories": ["Lawyers", "Advocates", "Chartered Accountants", "Tax Consultants", "Architects", "Insurance Agents"]
    },
    "Real Estate": {
        "subcategories": ["Estate Agents", "Property Developers", "Builders", "Apartment Rental", "Villa Rental", "Commercial Property", "Land & Plots", "PG Accommodation"]
    },
    "Shopping": {
        "subcategories": ["Clothing Stores", "Jewellery Showrooms", "Footwear Dealers", "Supermarkets", "Grocery Stores", "Furniture Dealers", "Electronic Goods", "Gift Shops"]
    },
    "Travel & Tourism": {
        "subcategories": ["Travel Agents", "Tour Operators", "Airline Ticketing Agents", "Railway Ticketing Agents", "Bus Services", "Car Rental", "Hotels"]
    },
    "Events & Weddings": {
        "subcategories": ["Wedding Planners", "Event Organisers", "Caterers", "Photographers", "Videographers", "Banquet Halls", "Decorators", "Flower Decorators"]
    },
    "Computer & IT": {
        "subcategories": ["Computer Training Institutes", "Software Companies", "IT Solution Providers", "Web Designing Services", "Computer Repair & Services", "Laptop Dealers"]
    }
}

# Cache file path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CATEGORIES_CACHE = os.path.join(project_root, "category_cache.json")


def get_main_categories():
    """Get list of all main categories"""
    return list(JUSTDIAL_MAIN_CATEGORIES.keys())


def get_subcategories(category):
    """Get subcategories for a main category"""
    if category in JUSTDIAL_MAIN_CATEGORIES:
        return JUSTDIAL_MAIN_CATEGORIES[category]["subcategories"]
    return []


def format_category_for_url(category):
    """Format category name for JustDial URL"""
    formatted = category.replace(" & ", "-").replace(" ", "-").replace("&", "-")
    return formatted.lower()


def save_categories_cache(data):
    """Save categories to cache"""
    with open(CATEGORIES_CACHE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_categories_cache():
    """Load categories from cache"""
    try:
        with open(CATEGORIES_CACHE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def fetch_categories_from_justdial(city="Kochi"):
    """Get categories (use our predefined list as primary, with caching)"""
    try:
        cached = load_categories_cache()
        if cached:
            return cached
        
        save_categories_cache(JUSTDIAL_MAIN_CATEGORIES)
        return JUSTDIAL_MAIN_CATEGORIES
    except Exception as e:
        print(f"Using default categories. Error: {e}")
        return JUSTDIAL_MAIN_CATEGORIES


def build_search_url(city, category, subcategory=None):
    """Build JustDial search URL"""
    city_formatted = format_category_for_url(city)
    cat_formatted = format_category_for_url(subcategory if subcategory else category)
    return f"https://www.justdial.com/{city_formatted}/{cat_formatted}"
