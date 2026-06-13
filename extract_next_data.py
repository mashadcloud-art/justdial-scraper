
import sys
import os
import json
from bs4 import BeautifulSoup

with open("debug_after_menu_click.html", "r", encoding="utf-8") as f:
    html = f.read()
    
soup = BeautifulSoup(html, "html.parser")

print("=== Looking for __NEXT_DATA__ ===")
next_data_script = None
for script in soup.find_all("script"):
    if script.get("id") == "__NEXT_DATA__":
        next_data_script = script
        break
        
if next_data_script:
    print("Found __NEXT_DATA__!")
    try:
        data = json.loads(next_data_script.string)
        results = data.get("props", {}).get("pageProps", {}).get("results", {}).get("results", {})
        
        # Save to a file
        with open("next_data_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print("Saved results to next_data_results.json!")
        
        # Print keys
        print("\nTop-level keys in results:")
        for key in sorted(results.keys()):
            print(f"  - {key}")
            
        # Check if there are menu items anywhere
        print("\nChecking for menu-related data...")
        def check_obj(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if "menu" in key.lower() or "item" in key.lower() or "food" in key.lower():
                        print(f"\nFound at {new_path}")
                        # Print first 2 items if it's a list
                        if isinstance(value, list) and len(value) > 0:
                            print(f"  First {min(2, len(value))} items:")
                            for i in range(min(2, len(value))):
                                print(f"    {i}: {str(value[i])[:300]}")
                        else:
                            print(f"  Value type: {type(value)}")
                            print(f"  Value preview: {str(value)[:300]}")
                    check_obj(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_obj(item, f"{path}[{i}]")
                    
        check_obj(results)
        
    except Exception as e:
        print(f"Error parsing __NEXT_DATA__: {e}")
        import traceback
        print(traceback.format_exc())
else:
    print("Could not find __NEXT_DATA__ script!")
