"""Slow, resumable DuckDuckGo HTML search for companies still missing a domain. usage: python3 ddg_search.py in.json out.jsonl"""
import json, os, sys, time, random
import requests
from selectolax.parser import HTMLParser

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
items = json.load(open(sys.argv[1]))
dst = sys.argv[2]
done = {json.loads(l)['id'] for l in open(dst)} if os.path.exists(dst) else set()
out = open(dst, 'a')
s = requests.Session()
s.headers.update({'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9', 'Referer': 'https://html.duckduckgo.com/'})
n = 0
for it in items:
    if it['id'] in done:
        continue
    res, status = None, 'blocked'
    for attempt in range(5):
        try:
            r = s.post('https://html.duckduckgo.com/html/', data={'q': it['q'], 'kl': 'us-en'}, timeout=25)
            h = HTMLParser(r.text)
            items_ = h.css('div.result')
            if r.status_code == 200 and (items_ or 'No results' in r.text):
                res = [dict(url=(d.css_first('a.result__a').attributes.get('href') if d.css_first('a.result__a') else ''),
                            title=(d.css_first('a.result__a').text() if d.css_first('a.result__a') else ''),
                            snippet=(d.css_first('.result__snippet').text() if d.css_first('.result__snippet') else '')[:250])
                       for d in items_[:10]]
                status = 'ok'
                break
        except Exception:
            pass
        time.sleep(30 + 30 * attempt + random.random() * 10)
    out.write(json.dumps(dict(id=it['id'], name=it['name'], q=it['q'], status=status, results=res or [])) + '\n'); out.flush()
    n += 1
    if n % 25 == 0:
        print(n, time.strftime('%H:%M'), flush=True)
    time.sleep(4 + random.random() * 4)
print('done', n)
