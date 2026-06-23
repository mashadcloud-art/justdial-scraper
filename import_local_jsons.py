import os
import sys
import json
import glob
from typing import List, Dict, Any

# Ensure project path is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.scraper.emulator_parser import process_emulator_json
from app.scraper.logger import log

def get_json_files(path: str) -> List[str]:
    """Get list of JSON files from a directory or a single file path."""
    if os.path.isfile(path):
        return [path]
    elif os.path.isdir(path):
        return glob.glob(os.path.join(path, "*.json"))
    return []

def import_json_files(source_path: str, district: str = "Unknown"):
    """
    Combines and imports JSON files from source_path (file or folder)
    directly into the SQLite database.
    """
    json_files = get_json_files(source_path)
    if not json_files:
        print(f"❌ No JSON files found at: {source_path}")
        return

    print(f"🔍 Found {len(json_files)} JSON file(s) to process:")
    for jf in json_files:
        print(f"  - {os.path.basename(jf)}")
    print("-" * 55)

    total_uploaded = 0
    for jf in json_files:
        print(f"\n📂 Processing: {os.path.basename(jf)}")
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Use emulator parser to ingest
            uploaded = process_emulator_json(data, district)
            total_uploaded += uploaded
            print(f"✅ Ingested {uploaded} restaurants from {os.path.basename(jf)}")
        except Exception as e:
            print(f"❌ Error processing {os.path.basename(jf)}: {e}")

    print("\n" + "=" * 55)
    print(f"🏁 Finished! Combined and uploaded a total of {total_uploaded} restaurants to the database.")
    print("=" * 55)

if __name__ == "__main__":
    import sys
    
    default_path = r"c:\Users\PC\Desktop\resturants.json"
    
    # Check if arguments are passed via command line
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
        target_district = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
    else:
        print("=== JustDial Local JSON Bulk Importer ===")
        path_input = input(f"Enter path to JSON file or folder (default: {default_path}): ").strip()
        target_path = path_input if path_input else default_path
        
        district_input = input("Enter default District name (e.g. Idukki, Kasaragod) [default: Unknown]: ").strip()
        target_district = district_input if district_input else "Unknown"
    
    if not os.path.exists(target_path):
        print(f"❌ Path does not exist: {target_path}")
        sys.exit(1)
        
    import_json_files(target_path, target_district)
