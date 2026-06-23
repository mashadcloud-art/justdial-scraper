import json
data = json.load(open('next_data.json'))
props = data['props']['pageProps']

results = []
if 'searchResultData' in props:
    try:
        items = props['searchResultData']['data']['data']
        for i in items:
            name = i.get("company_name", i.get("name", ""))
            results.append(name)
    except:
        pass

if 'search' in props:
    try:
        if type(props['search']) == dict:
            items = props['search'].get('data', [])
            for i in items:
                name = i.get("company_name", i.get("name", ""))
                if name: results.append(name)
        elif type(props['search']) == list:
            for i in props['search']:
                name = i.get("company_name", i.get("name", ""))
                if name: results.append(name)
    except Exception as e:
        print("Error search:", e)

if 'listData' in props:
    try:
        if type(props['listData']) == dict:
            items = props['listData'].get('data', [])
            for i in items:
                name = i.get("company_name", i.get("name", ""))
                if name: results.append(name)
        elif type(props['listData']) == list:
            for i in props['listData']:
                name = i.get("company_name", i.get("name", ""))
                if name: results.append(name)
    except Exception as e:
        print("Error listData:", e)

print("Names found:", len(results))
print(results[:5])
