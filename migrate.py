import sqlite3
import os

db_path = "data/justdial.db"
if not os.path.exists(db_path):
    # Try alternate path
    db_path = "justdial.db"

if os.path.exists(db_path):
    print(f"Migrating database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(restaurants)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "latitude" not in columns:
        print("Adding 'latitude' column...")
        cursor.execute("ALTER TABLE restaurants ADD COLUMN latitude VARCHAR(50)")
    if "longitude" not in columns:
        print("Adding 'longitude' column...")
        cursor.execute("ALTER TABLE restaurants ADD COLUMN longitude VARCHAR(50)")
        
    conn.commit()
    conn.close()
    print("Migration successful!")
else:
    print("No database file found to migrate. Columns will be created automatically on next launch.")
