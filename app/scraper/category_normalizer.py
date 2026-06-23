"""
category_normalizer.py
Maps raw JustDial categories (1,485+ unique strings) into ~16 parent groups.
Each listing keeps its specific raw category (e.g., "Salons", "Beauty Parlours")
but gets a normalized_category (e.g., "Beauty & Spas") for grouped search.

Usage:
    from app.scraper.category_normalizer import normalize_category
    parent = normalize_category("Hair Stylist For Men")  # -> "Beauty & Spas"
"""

# ============================================================
# MASTER MAPPING: parent_category -> list of keyword patterns
# Order matters: more specific patterns first, broader ones last.
# A raw category is matched to the FIRST parent whose keyword
# appears in the lowercased raw string.
# ============================================================

CATEGORY_KEYWORD_MAP = {
    # ── Beauty & Spas ──────────────────────────────────────
    "Beauty & Spas": [
        "beauty parlour", "beauty parlor", "beauty salon", "beauty spa",
        "bridal makeup", "bridal studio", "makeup artist", "makeup studio",
        "hair stylist", "hair cutting", "hair dressing", "hair treatment",
        "hair transplant", "hair salon", "hair studio", "hair care",
        "nail art", "nail spa", "nail extension",
        "salon", "saloon",
        "barber", "grooming",
        "parlour for", "parlours for",  # catches "Beauty Parlours For Bridal At Home" etc.
        "beauty", "beautician",
        "spa for", "spas for",
        "body massage", "massage centre", "massage center",
        "ayurvedic massage", "thai massage",
        "facial", "waxing", "threading",
        "tattoo", "mehndi", "henna",
        "cosmetolog",
        "unisex salon", "men salon", "women salon",
        "ladies beauty", "men beauty",
        "skin care clinic", "skin clinic",
        "dermatolog",
    ],

    # ── Hotels & Restaurants ───────────────────────────────
    "Hotels & Restaurants": [
        "restaurant", "multicuisine", "multi cuisine",
        "biryani", "pizza", "burger", "sandwich", "shawarma", "kebab",
        "fried chicken", "grilled chicken",
        "south indian", "north indian", "chinese food", "continental",
        "mughlai", "punjabi food", "gujarati food", "rajasthani food",
        "kerala food", "udupi",
        "dhaba", "mess",
        "fine dining", "family restaurant",
        "fast food", "street food",
        "bakery", "bakeries", "confectionery", "sweet shop", "sweet mart",
        "ice cream", "frozen dessert",
        "juice", "smoothie", "shake",
        "cafe", "coffee shop", "tea stall", "tea shop",
        "bar ", "lounge bar", "pub ", "wine shop", "liquor",
        "catering", "caterer", "tiffin", "cloud kitchen",
        "hotel", "resort", "guest house", "homestay", "home stay",
        "lodge", "motel", "service apartment", "serviced apartment",
        "paying guest", " pg ", "pg accommodation",
        "hostel",
        "banquet hall", "party hall", "marriage hall",
        "food", "snack",
    ],

    # ── Health & Medical ───────────────────────────────────
    "Health & Medical": [
        "hospital", "nursing home",
        "clinic", "polyclinic",
        "doctor", "physician", "surgeon", "specialist",
        "dentist", "dental",
        "eye ", "ophthal", "optician", "optical",
        "ent specialist", "ent doctor", "ortho", "cardio", "neuro", "gastro", "uro",
        "gynaecolog", "gynecolog", "obstetric",
        "paediatric", "pediatric",
        "dermatologist doctor",  # doctor-specific, not beauty
        "patholog", "diagnostic", "lab ", "laboratory",
        "x ray", "x-ray", "scan centre", "mri ", "ct scan",
        "pharmacy", "medical shop", "medical store", "chemist",
        "ayurvedic clinic", "ayurvedic hospital", "ayurvedic doctor",
        "homeopath", "unani", "siddha",
        "physiotherap", "rehab",
        "ambulance", "blood bank", "blood donor",
        "veterinary", "vet clinic", "vet hospital", "animal hospital",
        "mental health", "psychiatr", "psycholog",
        "fertility", "ivf",
        "nursing", "health care", "healthcare",
        "medical", "medic",
    ],

    # ── Education ──────────────────────────────────────────
    "Education": [
        "school", "cbse", "icse", "state board",
        "college", "university", "deemed university",
        "play school", "pre school", "preschool", "montessori", "kindergarten",
        "tutorial", "tuition", "coaching", "academy",
        "training institute", "training centre", "training center",
        "computer training", "language class",
        "mba ", "engineering college", "medical college",
        "polytechnic", "iti ",
        "overseas education", "study abroad",
        "competitive exam", "entrance exam",
        "music class", "dance class", "art class",
        "driving school", "driving class",
        "education consultant", "educational",
        "library", "book shop", "book store",
        "home tutor", "private tutor",
        "institute", "learning",
        "trust",
    ],

    # ── Automobiles ────────────────────────────────────────
    "Automobiles": [
        "car dealer", "car showroom",
        "second hand car", "used car",
        "car repair", "car service", "car mechanic", "car workshop",
        "car accessori", "car spare", "car part",
        "car wash", "car clean", "car polish", "car detailing",
        "two wheeler", "bike dealer", "motorcycle dealer", "scooter dealer",
        "bike repair", "bike service", "motorcycle repair",
        "tyre ", "tire ", "tubeless",
        "battery dealer", "car battery",
        "auto rickshaw", "auto dealer",
        "truck dealer", "truck repair", "trucks on rent",
        "bus dealer",
        "vehicle", "automobile",
        "petrol pump", "fuel station", "gas station",
        "driving licence", "rto ",
        "car rental", "bike on rent", "self drive",
    ],

    # ── Shopping ───────────────────────────────────────────
    "Shopping": [
        "clothing", "garment", "readymade", "ready made",
        "boutique", "fashion",
        "saree", "sari ", "kurti", "lehenga", "sherwani", "blazer",
        "dress material", "fabric",
        "jeweller", "gold ", "silver ", "diamond",
        "footwear", "shoe ", "sandal", "chappal",
        "watch ", "watches",
        "supermarket", "hypermarket", "departmental store",
        "grocery", "provision", "kirana",
        "fruit", "vegetable", "meat shop", "fish market", "fish stall",
        "flower shop", "florist",
        "gift shop", "toy shop", "stationery",
        "cosmetic", "perfume",
        "shopping mall", "shopping complex", "market",
        "handicraft", "handloom",
        "textile", "cloth",
        "utensil", "kitchenware",
        "general store", "fancy store",
        "bag ", "bags ", "luggage", "trolley bag",
        "optical showroom",
        "sports goods", "sports shop",
        "pet shop", "aquarium",
        "mobile phone dealer", "mobile shop",
        "electronic goods", "electronic showroom",
        "retailer", "wholesaler", "distributor",
    ],

    # ── Home Services ──────────────────────────────────────
    "Home Services": [
        "packers", "movers", "relocation",
        "pest control",
        "electrician", "electrical contractor",
        "plumber", "plumbing",
        "carpenter", "carpentry",
        "ac repair", "ac service", "air condition",
        "refrigerator repair", "fridge repair",
        "washing machine repair",
        "water purifier", "ro service",
        "home cleaning", "house cleaning", "deep cleaning",
        "painting contractor", "house paint",
        "waterproof", "water tank",
        "borewell", "borehole",
        "solar panel", "solar power", "solar install",
        "security guard", "security service",
        "cctv", "surveillance",
        "alarm system",
        "locksmith", "key maker",
        "home appliance repair",
        "gas connection", "gas agency", "lpg",
        "laundry", "dry clean", "ironing",
    ],

    # ── Real Estate ────────────────────────────────────────
    "Real Estate": [
        "estate agent", "real estate", "property dealer",
        "property developer", "builder", "promoter",
        "apartment rental", "flat rental", "house rental",
        "villa rental", "villa for",
        "commercial property", "office space",
        "land ", "plot ", "site for sale",
        "pg accommodation", "paying guest",
        "warehouse", "godown",
        "construction contractor", "civil contractor",
        "architect",
    ],

    # ── Travel & Tourism ──────────────────────────────────
    "Travel & Tourism": [
        "travel agent", "travel agency",
        "tour operator", "tour package",
        "airline", "flight booking",
        "railway", "train ticket",
        "bus service", "bus booking", "bus operator",
        "cab ", "taxi ", "call taxi",
        "tempo traveller", "traveller on rent",
        "passport", "visa ", "forex",
        "cruise",
        "tourism", "tourist",
        "transport", "courier", "cargo", "logistics",
    ],

    # ── Events & Weddings ─────────────────────────────────
    "Events & Weddings": [
        "wedding planner", "marriage planner",
        "event organis", "event manag",
        "photographer", "photography", "videograph",
        "decorator", "flower decorator", "stage decorator",
        "mandap", "pandal",
        "dj ", "disc jockey", "sound system",
        "choreograph",
        "photo studio", "photo frame",
        "invitation card", "printing press",
        "costume", "costumes on rent",
        "shamiyana", "tent ", "tents on rent",
        "matchmak", "matching center",
    ],

    # ── Legal & Professional Services ─────────────────────
    "Legal & Professional Services": [
        "lawyer", "advocate", "attorney",
        "chartered accountant", "ca firm",
        "tax consultant", "tax advisor",
        "company secretary",
        "notary", "affidavit",
        "patent", "trademark",
        "consultant", "consultancy",
        "auditor", "accounting",
        "hr ", "recruitment", "placement", "manpower",
        "detective", "investigation",
    ],

    # ── Computer & IT ─────────────────────────────────────
    "Computer & IT": [
        "software", "it company", "it solution",
        "web design", "web develop", "website",
        "app develop", "mobile app",
        "computer repair", "computer service",
        "laptop repair", "laptop dealer",
        "printer repair", "printer dealer",
        "data recovery", "data entry",
        "computer", "networking",
        "digital marketing", "seo ",
        "graphic design",
    ],

    # ── Home Decor & Furnishing ───────────────────────────
    "Home Decor & Furnishing": [
        "furniture dealer", "furniture manufacturer", "furniture shop",
        "sofa ", "sofa set", "sofa cum bed",
        "bed dealer", "bedroom furniture", "mattress",
        "modular kitchen", "kitchen cabinet",
        "wardrobe", "almirah", "cupboard",
        "curtain", "blind ", "window blind",
        "carpet", "rug ", "floor mat",
        "wallpaper", "wall decor", "wall panel",
        "lamp ", "lighting", "chandelier",
        "home decor", "interior design", "interior decorator",
        "antique furniture",
        "office furniture", "wooden",
        "pillow", "cushion",
        "furnish",
        "plywood", "timber", "wood",
    ],

    # ── Entertainment & Fitness ───────────────────────────
    "Entertainment & Fitness": [
        "cinema", "theatre", "theater", "movie",
        "gaming zone", "game parlour", "video game",
        "amusement park", "water park", "theme park",
        "sports club", "cricket", "football", "badminton", "tennis",
        "gym ", "gymnasium", "fitness",
        "yoga ", "zumba", "aerobics",
        "swimming pool", "swimming class",
        "martial art", "karate", "taekwondo",
        "billiard", "bowling",
        "adventure", "trekking",
        "club ",
    ],

    # ── Banks & Financial Services ────────────────────────
    "Banks & Financial Services": [
        "bank ", "banking",
        "atm ",
        "loan ", "personal loan", "home loan", "business loan",
        "credit card",
        "insurance", "lic ", "life insurance",
        "mutual fund", "investment",
        "stock broker", "share broker",
        "money transfer", "money exchange",
        "gold loan", "chit fund",
        "microfinance", "nbfc",
        "financial",
    ],

    # ── Electronics & Electrical ──────────────────────────
    "Electronics & Electrical": [
        "electrical shop", "electrical dealer",
        "hardware shop", "hardware dealer",
        "paint shop", "paint dealer", "asian paint",
        "sanitary", "bathroom fitting", "bath fitting",
        "cement", "steel ", "iron ",
        "building material", "construction material",
        "tile ", "tiles ", "marble", "granite",
        "glass ", "aluminium", "aluminum",
        "pvc ", "pipe ", "piping",
        "welding", "fabricat",
        "generator", "inverter", "ups ",
        "led ", "bulb ", "fan dealer", "fan regulator",
        "wire ", "cable ", "switch ",
        "transformer", "motor ",
        "pump ", "compressor",
        "sign board",
    ],

    # ── Government & Utilities ────────────────────────────
    "Government & Utilities": [
        "government", "govt ",
        "post office", "police", "fire station",
        "municipality", "panchayat", "corporation",
        "water supply", "electricity board",
        "ration shop",
        "aadhar", "aadhaar",
        "passport office",
        "court ",
        "ngo ", "charitable",
    ],
}


def normalize_category(raw_category: str) -> str:
    """
    Maps a raw JustDial category string to a parent normalized category.
    
    Examples:
        normalize_category("Beauty Parlours For Bridal At Home") -> "Beauty & Spas"
        normalize_category("Hair Stylist For Men") -> "Beauty & Spas"
        normalize_category("Salons") -> "Beauty & Spas"
        normalize_category("Fried Chicken Restaurants") -> "Hotels & Restaurants"
        normalize_category("Mattress Dealers") -> "Home Decor & Furnishing"
    """
    if not raw_category:
        return "Other"
    
    raw_lower = raw_category.lower().strip()
    
    if not raw_lower:
        return "Other"
    
    # Check each parent category's keywords
    for parent, keywords in CATEGORY_KEYWORD_MAP.items():
        for keyword in keywords:
            if keyword in raw_lower:
                return parent
    
    return "Other"


def get_all_parent_categories() -> list:
    """Returns list of all parent category names."""
    return list(CATEGORY_KEYWORD_MAP.keys())


def get_category_keywords(parent: str) -> list:
    """Returns keywords for a specific parent category."""
    return CATEGORY_KEYWORD_MAP.get(parent, [])


# Quick self-test
if __name__ == "__main__":
    test_cases = [
        "Beauty Parlours",
        "Salons",
        "Hair Stylist For Men",
        "Body Massage Centres",
        "Beauty Spas For Women",
        "Makeup Artists",
        "Beauty Parlours For Nail Art",
        "Children Beauty Parlours",
        "Beauty Parlours For Bridal At Home",
        "Men Beauty Parlours",
        "Restaurants",
        "Fried Chicken Restaurants",
        "Hospitals",
        "Clinics",
        "Schools",
        "Furniture Dealers",
        "Mattress Dealers",
        "Car Rental",
        "Readymade Garment Retailers",
        "Hostels",
        "Costumes On Rent",
        "Interior Designers",
        "Electrical Shops",
        "Shopping Malls",
        "Hardware Shops",
        "Antique Furniture Dealers",
        "Bed Dealers",
        "Bedroom Furniture Dealers",
        "Hotels",
        "Bakeries",
        "Colleges",
        "Educational Institutes",
        "Bike On Rent",
        "Motorcycle Dealers",
        "Cotton Fabric Wholesalers",
        "Yemeni Restaurants",
        "Laundry Services",
        "Photo Studios",
        "General Stores",
    ]
    
    print("=== CATEGORY NORMALIZER TEST ===\n")
    for tc in test_cases:
        result = normalize_category(tc)
        print(f"  {tc:50} -> {result}")
