"""
data_quality_audit.py - Quick audit of data quality in Supabase
"""
import sys; sys.path.insert(0, '.')
from sqlalchemy import create_engine, text

engine = create_engine(
    'postgresql://postgres:HEERnuh%402025@db.qdsjbfhjzyypfyryjqxp.supabase.co:5432/postgres',
    pool_pre_ping=True
)

with engine.connect() as conn:
    total = conn.execute(text("SELECT COUNT(*) FROM restaurants")).scalar()
    print(f"\n=== DATA QUALITY AUDIT ({total} records) ===\n")

    # Missing fields
    no_phone  = conn.execute(text("SELECT COUNT(*) FROM restaurants WHERE phone IS NULL OR phone = ''")).scalar()
    no_state  = conn.execute(text("SELECT COUNT(*) FROM restaurants WHERE state IS NULL OR state = ''")).scalar()
    no_dist   = conn.execute(text("SELECT COUNT(*) FROM restaurants WHERE district IS NULL OR district = ''")).scalar()
    no_place  = conn.execute(text("SELECT COUNT(*) FROM restaurants WHERE place IS NULL OR place = ''")).scalar()
    no_subcat = conn.execute(text("SELECT COUNT(*) FROM restaurants WHERE subcategory IS NULL OR subcategory = ''")).scalar()
    no_addr   = conn.execute(text("SELECT COUNT(*) FROM restaurants WHERE address IS NULL OR address = ''")).scalar()
    no_cat    = conn.execute(text("SELECT COUNT(*) FROM restaurants WHERE category IS NULL OR category = ''")).scalar()

    def pct(n): return f"{round(n/total*100,1)}%" if total else "0%"

    print(f"[FIELDS MISSING]")
    print(f"  No phone      : {no_phone:>6} ({pct(no_phone)})")
    print(f"  No state      : {no_state:>6} ({pct(no_state)})")
    print(f"  No district   : {no_dist:>6} ({pct(no_dist)})")
    print(f"  No place      : {no_place:>6} ({pct(no_place)})")
    print(f"  No subcategory: {no_subcat:>6} ({pct(no_subcat)})")
    print(f"  No address    : {no_addr:>6} ({pct(no_addr)})")
    print(f"  No category   : {no_cat:>6} ({pct(no_cat)})")

    # Category breakdown
    print(f"\n[CATEGORY BREAKDOWN] (top 10)")
    rows = conn.execute(text(
        "SELECT category, COUNT(*) as cnt FROM restaurants GROUP BY category ORDER BY cnt DESC LIMIT 10"
    )).fetchall()
    for r in rows:
        print(f"  {(r[0] or '(empty)'):40} : {r[1]}")

    # State breakdown
    print(f"\n[STATE BREAKDOWN]")
    rows = conn.execute(text(
        "SELECT state, COUNT(*) as cnt FROM restaurants GROUP BY state ORDER BY cnt DESC LIMIT 10"
    )).fetchall()
    for r in rows:
        print(f"  {(r[0] or '(no state)'):30} : {r[1]}")

    # District breakdown
    print(f"\n[DISTRICT BREAKDOWN] (top 10)")
    rows = conn.execute(text(
        "SELECT district, COUNT(*) as cnt FROM restaurants GROUP BY district ORDER BY cnt DESC LIMIT 10"
    )).fetchall()
    for r in rows:
        print(f"  {(r[0] or '(no district)'):30} : {r[1]}")

    # Sample records
    print(f"\n[SAMPLE RECORDS]")
    rows = conn.execute(text(
        "SELECT name, category, subcategory, place, district, state FROM restaurants LIMIT 5"
    )).fetchall()
    for r in rows:
        print(f"  Name     : {r[0]}")
        print(f"  Category : {r[1]} | Sub: {r[2]} | Place: {r[3]}")
        print(f"  Location : {r[5]} > {r[4]}")
        print()
