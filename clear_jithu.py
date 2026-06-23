import sqlite3

conn = sqlite3.connect("data/justdial.db")
cursor = conn.cursor()

# Find restaurant ID dynamically
cursor.execute("SELECT id FROM restaurants WHERE name LIKE '%Jithu%'")
rows = cursor.fetchall()
if rows:
    for row in rows:
        r_id = row[0]
        print(f"Deleting restaurant ID {r_id}...")
        cursor.execute("DELETE FROM menu_items WHERE restaurant_id = ?", (r_id,))
        cursor.execute("DELETE FROM restaurant_images WHERE restaurant_id = ?", (r_id,))
        cursor.execute("DELETE FROM amenities WHERE restaurant_id = ?", (r_id,))
        cursor.execute("DELETE FROM restaurants WHERE id = ?", (r_id,))
    conn.commit()
    print("Deleted Jithu records successfully.")
else:
    print("No Jithu records found in DB.")

conn.close()
