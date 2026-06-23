import sqlite3
import os

DATA_DB = os.path.join("data", "justdial.db")
conn = sqlite3.connect(DATA_DB)
c = conn.cursor()

names = ["Hotel Shaan", "Ksd Restaurant", "Arabian Food Box", "Shreejith Kitchen",
         "Chandragiri Live Fish Fry", "Khaleej Sea Foodland", "Hotel Sinan",
         "Hotel Udayagiri", "Life Line Hotel", "Kallum Kadav"]

print("Kasaragod restaurants in data/justdial.db:\n")
for name in names:
    c.execute("SELECT id, name, phone, address FROM restaurants WHERE name = ?", (name,))
    row = c.fetchone()
    if row:
        print(f"  ✅ FOUND  | ID:{row[0]} | {row[1]} | Phone:{row[2]} | {row[3][:50]}")
    else:
        print(f"  ❌ MISSING: {name}")

conn.close()
