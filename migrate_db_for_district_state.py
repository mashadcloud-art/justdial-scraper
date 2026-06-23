import sqlite3
import os

db_paths = [
    os.path.join(os.path.dirname(__file__), "justdial.db"),
    os.path.join(os.path.dirname(__file__), "data", "justdial.db")
]

for db_path in db_paths:
    if os.path.exists(db_path):
        print(f"Checking database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(restaurants)")
            columns = [col[1] for col in cursor.fetchall()]

            if "district" not in columns:
                print("  Adding missing district column...")
                cursor.execute("ALTER TABLE restaurants ADD COLUMN district VARCHAR(100) DEFAULT ''")
                conn.commit()
                print("  District column added!")
            else:
                print("  District column already exists!")

            if "state" not in columns:
                print("  Adding missing state column...")
                cursor.execute("ALTER TABLE restaurants ADD COLUMN state VARCHAR(100) DEFAULT ''")
                conn.commit()
                print("  State column added!")
            else:
                print("  State column already exists!")

        except Exception as e:
            print(f"  Error: {e}")
        finally:
            conn.close()
    else:
        print(f"Database does not exist yet at: {db_path}")

print("Migration completed!")
