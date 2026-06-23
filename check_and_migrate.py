import sqlite3
import os

ROOT_DB = "justdial.db"
DATA_DB = os.path.join("data", "justdial.db")

print("=== Checking data/justdial.db ===")
conn = sqlite3.connect(DATA_DB)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in c.fetchall()]
print("Tables:", tables)
for t in tables:
    c.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"  {t}: {c.fetchone()[0]} rows")
conn.close()

print("\n=== Checking root justdial.db ===")
conn2 = sqlite3.connect(ROOT_DB)
c2 = conn2.cursor()
c2.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables2 = [t[0] for t in c2.fetchall()]
print("Tables:", tables2)
for t in tables2:
    c2.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"  {t}: {c2.fetchone()[0]} rows")
conn2.close()
