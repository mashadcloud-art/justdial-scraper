import sys
import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# This ensures Python can find the 'config.py' file in the root folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

DATABASE_URL = settings.DATABASE_URL
is_postgres = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")

# Create the database engine
if is_postgres:
    # PostgreSQL / Supabase — use connection pooling for performance
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,       # Test connections before using them
        pool_recycle=300,         # Recycle connections every 5 minutes
        connect_args={
            "connect_timeout": 10,
            "options": "-c timezone=utc"
        }
    )
    print("[OK] Connected to Supabase PostgreSQL cloud database!")
else:
    # SQLite fallback (local)
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, connect_args=connect_args)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.close()
    print("[WARN] Using local SQLite database.")

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