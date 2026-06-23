import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect("justdial.db")
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables in DB:")
for t in tables:
    table_name = t[0]
    print(f"\nTable: {table_name}")
    cursor.execute(f"PRAGMA table_info({table_name})")
    for col in cursor.fetchall():
        print("  ", col)
        
conn.close()
