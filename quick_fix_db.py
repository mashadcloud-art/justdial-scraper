import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "justdial.db")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(restaurants)")
        columns = [col[1] for col in cursor.fetchall()]

        if "category" not in columns:
            print("Adding missing category column...")
            cursor.execute("ALTER TABLE restaurants ADD COLUMN category TEXT DEFAULT ''")
            conn.commit()
            print("Database fixed! Category column added!")
        else:
            print("Database already has category column!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
else:
    print("No database yet, no problem!")
