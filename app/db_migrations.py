"""
Database Migration System
Automatically handles schema changes and table renames to prevent
mismatches between models and actual database tables.
"""
import sqlite3
from sqlalchemy import inspect, text
from app.database import engine, Base, is_postgres
from app import models


def get_existing_tables():
    """Get list of existing tables in the database"""
    if is_postgres:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            return {row[0] for row in result}
    else:
        # SQLite
        inspector = inspect(engine)
        return set(inspector.get_table_names())


def get_model_tables():
    """Get list of tables defined in models"""
    return {cls.__tablename__ for cls in Base.__subclasses__()}


def run_migrations():
    """
    Run automatic migrations to ensure database schema matches models.
    This handles table renames and missing tables.
    """
    existing_tables = get_existing_tables()
    model_tables = get_model_tables()
    
    print(f"[Migration] Existing tables: {existing_tables}")
    print(f"[Migration] Model tables: {model_tables}")
    
    # Table name mappings for backward compatibility
    table_mappings = {
        'restaurants': 'listings',
        'restaurant_images': 'listing_images',
    }
    
    migrations_run = []
    
    # Check for tables that need renaming
    for old_name, new_name in table_mappings.items():
        if old_name in existing_tables and new_name not in existing_tables:
            print(f"[Migration] Renaming table '{old_name}' to '{new_name}'")
            try:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))
                    else:
                        conn.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))
                migrations_run.append(f"Renamed {old_name} -> {new_name}")
                existing_tables.remove(old_name)
                existing_tables.add(new_name)
            except Exception as e:
                print(f"[Migration] Error renaming {old_name}: {e}")
    
    # Create missing tables
    with engine.connect() as conn:
        for table_name in model_tables:
            if table_name not in existing_tables:
                print(f"[Migration] Creating missing table: {table_name}")
                try:
                    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables[table_name]])
                    migrations_run.append(f"Created table {table_name}")
                except Exception as e:
                    print(f"[Migration] Error creating {table_name}: {e}")
    
    # Add missing columns to existing tables (SQLite-safe approach)
    if not is_postgres:
        inspector = inspect(engine)
        for table_name in existing_tables:
            if table_name in model_tables:
                model = next((cls for cls in Base.__subclasses__() if cls.__tablename__ == table_name), None)
                if model:
                    existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
                    model_columns = {col.name for col in model.__table__.columns}
                    
                    for col_name in model_columns - existing_columns:
                        print(f"[Migration] Adding column '{col_name}' to table '{table_name}'")
                        try:
                            column = next(col for col in model.__table__.columns if col.name == col_name)
                            col_type = column.type.compile(dialect=engine.dialect)
                            default = ""
                            if column.default is not None:
                                default = f" DEFAULT {column.default.arg}"
                            
                            with engine.begin() as conn:
                                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{default}"))
                            migrations_run.append(f"Added column {col_name} to {table_name}")
                        except Exception as e:
                            print(f"[Migration] Error adding column {col_name}: {e}")
    
    if migrations_run:
        print(f"[Migration] Completed {len(migrations_run)} migrations:")
        for migration in migrations_run:
            print(f"  - {migration}")
    else:
        print("[Migration] No migrations needed - database is up to date")
    
    return len(migrations_run) > 0


if __name__ == "__main__":
    print("Running database migrations...")
    run_migrations()
    print("Migration check complete.")
