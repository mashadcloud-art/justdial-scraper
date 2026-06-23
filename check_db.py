import sqlite3

db = sqlite3.connect('justdial.db')
db.row_factory = sqlite3.Row

rows = db.execute("""SELECT name, phone, address, category, district 
                     FROM restaurants WHERE district LIKE '%Kasaragod%' OR address LIKE '%Kasaragod%' 
                     ORDER BY id DESC LIMIT 20""").fetchall()
print(f"Found {len(rows)} Kasaragod entries")
for r in rows:
    name = r["name"]
    phone = r["phone"]
    addr = r["address"]
    cat = r["category"]
    print(f"  {name} | Ph: {phone} | Addr: {addr} | Cat: {cat}")

db.close()
