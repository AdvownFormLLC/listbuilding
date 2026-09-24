"""Fetch homepages for a list of hosts and store what each site says about itself.

usage: python3 fetch_sites.py hosts.txt out.jsonl
Each output line: {host, ok, status, final_url, title, desc, text, parked, err}
Already-fetched hosts in out.jsonl are skipped, so the script can be re-run to resume.
"""
import asyncio, json, os, re, ssl, sys

import aiohttp
from selectolax.parser import HTMLParser

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
PARKED = re.compile(r'domain (is|may be) for sale|buy this domain|this domain is parked|parked free|hugedomains|sedo\.com|dan\.com|'
                    r'afternic|domain name is for sale|inquire about this domain|godaddy\.com/domains|'
                    r'future home of something quite cool|website coming soon|under construction|account suspended|'
                    r'this site can.t be reached|default web site page|welcome to nginx|apache2 (ubuntu|debian) default page|'
                    r'index of /', re.I)
CONC = int(os.environ.get('CONC', 60))


def extract(html):
    h = HTMLParser(html)
    title = (h.css_first('title').text() if h.css_first('title') else '').strip()
    desc = ''
    for m in h.css('meta'):
        n = (m.attributes.get('name') or m.attributes.get('property') or '').lower()
        if n in ('description', 'og:description') and m.attributes.get('content'):
            desc = m.attributes['content'].strip(); break
    site_name = ''
    for m in h.css('meta[property="og:site_name"]'):
        site_name = (m.attributes.get('content') or '').strip()
    for t in h.css('script, style, noscript, svg'):
        t.decompose()
    body = h.body.text(separator=' ') if h.body else ''
    body = re.sub(r'\s+', ' ', body).strip()
    # keep the start of the page and the footer (addresses/phones usually live there)
    text = body[:2500] + (' … ' + body[-1200:] if len(body) > 3700 else body[2500:3700])
    return title, desc, site_name, text


async def fetch(session, host):
    last_err = ''
    for url in (f'https://{host}/', f'https://www.{host}/', f'http://{host}/'):
        if host.startswith('www.') and '://www.' in url:
            continue
        try:
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=25)) as r:
                raw = b''
                async for chunk in r.content.iter_chunked(65536):
                    raw += chunk
                    if len(raw) > 1_500_000:
                        break
                html = raw.decode(r.charset or 'utf-8', errors='ignore')
                title, desc, site_name, text = extract(html)
                lander = bool(re.search(r'location\.href\s*=\s*["\']/lander|/lander["\']|sgcaptcha|parkingcrew|bodis\.com|above\.com/', html[:5000]))
                blob = ' '.join((title, desc, text))
                return dict(host=host, ok=r.status < 400, status=r.status, final_url=str(r.url), title=title[:200],
                            desc=desc[:400], site_name=site_name[:100], text=text, parked=bool(PARKED.search(blob[:3000])) or ('lander' in html[:5000] and len(text) < 80),
                            captcha='sgcaptcha' in html[:3000], cf_challenge=('Just a moment' in title or 'Attention Required' in title), err='')
        except Exception as e:  # noqa: BLE001 - record and try next URL form
            last_err = f'{type(e).__name__}: {str(e)[:120]}'
    return dict(host=host, ok=False, status=0, final_url='', title='', desc='', site_name='', text='', parked=False,
                cf_challenge=False, err=last_err)


async def main(src, dst):
    hosts = [h.strip().lower() for h in open(src) if h.strip()]
    done = set()
    if os.path.exists(dst):
        for line in open(dst):
            try: done.add(json.loads(line)['host'])
            except Exception: pass
    todo = [h for h in dict.fromkeys(hosts) if h not in done]
    print(f'{len(todo)} to fetch ({len(done)} already done)', flush=True)
    ctx = ssl.create_default_context(cafile='/root/.ccr/ca-bundle.crt')
    conn = aiohttp.TCPConnector(limit=CONC, ssl=ctx, ttl_dns_cache=300)
    q = asyncio.Queue()
    for h in todo: q.put_nowait(h)
    out = open(dst, 'a')
    n = 0
    async with aiohttp.ClientSession(connector=conn, trust_env=True, headers={'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9',
                                     'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8'}) as s:
        async def worker():
            nonlocal n
            while not q.empty():
                h = q.get_nowait()
                res = await fetch(s, h)
                out.write(json.dumps(res) + '\n'); out.flush()
                n += 1
                if n % 500 == 0: print(n, flush=True)
        await asyncio.gather(*[worker() for _ in range(CONC)])
    print('done', n)


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], sys.argv[2]))
