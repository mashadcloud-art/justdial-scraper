import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# This ensures Python can find the 'config.py' file in the root folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

# Create the database engine
engine = create_engine(settings.DATABASE_URL)

# Create a session to interact with the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our database models
Base = declarative_base()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()