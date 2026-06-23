import json
data = json.load(open('next_data.json'))

def find_companies(d, path=''):
    if isinstance(d, dict):
        if 'name' in d and d['name']:
            print(path, '->', str(d['name'])[:50])
        for k, v in d.items():
            find_companies(v, path + '.' + str(k))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            find_companies(v, path + '[' + str(i) + ']')

find_companies(data)
