import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.database import SessionLocal
from app.models import Category

db = SessionLocal()
cats = db.query(Category).all()
for c in cats[:10]:
    print(c.name, c.jd_url)
