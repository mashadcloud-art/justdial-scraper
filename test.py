import requests, json, bs4
r=requests.get('https://www.justdial.com/Idukki/Fast-Food', headers={'User-Agent': 'Mozilla/5.0'})
soup=bs4.BeautifulSoup(r.text, 'html.parser')
script = soup.find('script', id='__NEXT_DATA__')
if script:
    data = json.loads(script.string)
    print(list(data['props']['pageProps'].keys()))
    if 'searchResultData' in data['props']['pageProps']:
        print(list(data['props']['pageProps']['searchResultData'].keys()))
else:
    print("No script")
