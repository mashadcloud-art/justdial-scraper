import urllib.request
import json

data = json.loads(urllib.request.urlopen('https://raw.githubusercontent.com/sab99r/Indian-States-And-Districts/master/states-and-districts.json').read().decode('utf-8'))

states = []
cities_py = 'CITIES = {\n    "All": ["All"],\n'
cities_ts = 'const CITIES: Record<string, string[]> = {\n  All: ["All"],\n'

for s in data['states']:
    state_name = s['state']
    states.append(f'"{state_name}"')
    dists = ['"All"'] + ['"'+d+'"' for d in s['districts']]
    cities_py += f'    "{state_name}": [{", ".join(dists)}],\n'
    cities_ts += f'  "{state_name}": [{", ".join(dists)}],\n'

cities_py += '}\n'
cities_ts += '};\n'

open('cities_py.txt', 'w', encoding='utf-8').write(cities_py)
open('cities_ts.txt', 'w', encoding='utf-8').write(cities_ts)

ts_states = 'const STATES = [\n  "All",\n  ' + ',\n  '.join([', '.join(states[i:i+5]) for i in range(0, len(states), 5)]) + '\n];\n'
open('states.txt', 'w', encoding='utf-8').write(ts_states)
