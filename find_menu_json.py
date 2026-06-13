
import sys
import os
import json
from bs4 import BeautifulSoup

with open("debug_after_menu_click.html", "r", encoding="utf-8") as f:
    html = f.read()
    
soup = BeautifulSoup(html, "html.parser")

print("=== Looking for JSON in script tags ===")
for script in soup.find_all("script"):
    text = script.get_text(strip=True)
    if text.startswith("{") or text.startswith("["):
        print(f"\nFound possible JSON script:")
        try:
            data = json.loads(text)
            print("  Successfully parsed as JSON!")
            # Try to find any menu-related data recursively
            def find_menu(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        new_path = f"{path}.{key}" if path else key
                        if "menu" in key.lower() or "item" in key.lower() or "food" in key.lower():
                            print(f"\n  Found key at {new_path}: {key}")
                            print(f"  Value preview: {str(value)[:200]}")
                        find_menu(value, new_path)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        new_path = f"{path}[{i}]"
                        find_menu(item, new_path)
            
            find_menu(data)
        except Exception as e:
            print(f"  Failed to parse JSON: {e}")
            # Maybe it's a window assignment like window.__NEXT_DATA__ = ...
            if "=" in text:
                parts = text.split("=", 1)
                if len(parts) > 1:
                    possible_json = parts[1].rstrip(";").strip()
                    try:
                        data = json.loads(possible_json)
                        print(f"  Successfully parsed after stripping assignment!")
                        def find_menu(obj, path=""):
                            if isinstance(obj, dict):
                                for key, value in obj.items():
                                    new_path = f"{path}.{key}" if path else key
                                    if "menu" in key.lower() or "item" in key.lower() or "food" in key.lower():
                                        print(f"\n  Found key at {new_path}: {key}")
                                        print(f"  Value preview: {str(value)[:300]}")
                                    find_menu(value, new_path)
                            elif isinstance(obj, list):
                                for i, item in enumerate(obj):
                                    new_path = f"{path}[{i}]"
                                    find_menu(item, new_path)
                        find_menu(data)
                    except Exception as e2:
                        print(f"  Still failed: {e2}")

print("\n=== Done ===")
