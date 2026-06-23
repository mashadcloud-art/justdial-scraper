import re

# 1. Update index.tsx
with open('ui/src/routes/index.tsx', 'r', encoding='utf-8') as f:
    ts_content = f.read()

with open('states.txt', 'r', encoding='utf-8') as f:
    new_states = f.read()

with open('cities_ts.txt', 'r', encoding='utf-8') as f:
    new_cities_ts = f.read()

# Replace STATES
ts_content = re.sub(r'const STATES = \[\s*[\s\S]*?\];\n', new_states, ts_content, count=1)

# Replace CITIES
ts_content = re.sub(r'const CITIES: Record<string, string\[\]> = \{\s*[\s\S]*?\};\n', new_cities_ts, ts_content, count=1)

with open('ui/src/routes/index.tsx', 'w', encoding='utf-8') as f:
    f.write(ts_content)

# 2. Update constants.py
with open('app/scraper/constants.py', 'r', encoding='utf-8') as f:
    py_content = f.read()

with open('cities_py.txt', 'r', encoding='utf-8') as f:
    new_cities_py = f.read()

py_content = re.sub(r'CITIES = \{\s*[\s\S]*?\}\n', new_cities_py, py_content, count=1)

with open('app/scraper/constants.py', 'w', encoding='utf-8') as f:
    f.write(py_content)

print("Injected successfully!")
