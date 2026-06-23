import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine, text

engine = create_engine(
    'postgresql://postgres:HEERnuh%402025@db.qdsjbfhjzyypfyryjqxp.supabase.co:5432/postgres',
    pool_pre_ping=True
)

with engine.connect() as conn:
    total = conn.execute(text('SELECT COUNT(*) FROM restaurants')).scalar()
    print(f'Total records in Supabase: {total}')
    
    rows = conn.execute(text(
        "SELECT state, COUNT(*) as cnt FROM restaurants GROUP BY state ORDER BY cnt DESC LIMIT 15"
    )).fetchall()
    print('--- By State ---')
    for row in rows:
        state = row[0] if row[0] else '(no state yet)'
        print(f'  {state}: {row[1]}')
