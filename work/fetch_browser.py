"""Re-fetch hosts that blocked plain HTTP (Cloudflare challenge, 403/429, timeouts) with headless Chromium.

usage: python3 fetch_browser.py hosts.txt out.jsonl   (same record format as fetch_sites.py; resumable)
"""
import asyncio, json, os, sys

from playwright.async_api import async_playwright

from fetch_sites import PARKED, extract

CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
CONC = int(os.environ.get('CONC', 10))


async def grab(ctx, host):
    pg = await ctx.new_page()
    try:
        last = ''
        for url in (f'https://{host}/', f'https://www.{host}/', f'http://{host}/'):
            try:
                r = await pg.goto(url, timeout=30000, wait_until='domcontentloaded')
                for _ in range(4):  # let Cloudflare's JS challenge finish
                    title = await pg.title()
                    if 'Just a moment' not in title and 'Attention Required' not in title:
                        break
                    await pg.wait_for_timeout(3000)
                await pg.wait_for_timeout(1500)
                html = await pg.content()
                title, desc, site_name, text = extract(html)
                status = r.status if r else 0
                cf = 'Just a moment' in title or 'Attention Required' in title
                blob = ' '.join((title, desc, text))
                return dict(host=host, ok=(status < 400 or len(text) > 400) and not cf, status=status, final_url=pg.url,
                            title=title[:200], desc=desc[:400], site_name=site_name[:100], text=text,
                            parked=bool(PARKED.search(blob[:3000])), cf_challenge=cf, err='', via='browser')
            except Exception as e:  # noqa: BLE001
                last = f'{type(e).__name__}: {str(e)[:120]}'
        return dict(host=host, ok=False, status=0, final_url='', title='', desc='', site_name='', text='', parked=False,
                    cf_challenge=False, err=last, via='browser')
    finally:
        await pg.close()


async def main(src, dst):
    hosts = [h.strip() for h in open(src) if h.strip()]
    done = set()
    if os.path.exists(dst):
        done = {json.loads(l)['host'] for l in open(dst)}
    todo = [h for h in dict.fromkeys(hosts) if h not in done]
    print(len(todo), 'to fetch', flush=True)
    q = asyncio.Queue()
    for h in todo: q.put_nowait(h)
    out = open(dst, 'a')
    n = 0
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
                                    proxy={'server': os.environ['HTTPS_PROXY']})

        async def worker():
            nonlocal n
            ctx = await b.new_context(ignore_https_errors=True, locale='en-US', user_agent=UA)
            await ctx.route('**/*', lambda r: r.abort() if r.request.resource_type in ('image', 'font', 'media') else r.continue_())
            while not q.empty():
                h = q.get_nowait()
                try:
                    res = await asyncio.wait_for(grab(ctx, h), 120)
                except Exception as e:  # noqa: BLE001
                    res = dict(host=h, ok=False, status=0, final_url='', title='', desc='', site_name='', text='', parked=False,
                               cf_challenge=False, err=f'{type(e).__name__}', via='browser')
                out.write(json.dumps(res) + '\n'); out.flush()
                n += 1
                if n % 100 == 0: print(n, flush=True)
            await ctx.close()
        await asyncio.gather(*[worker() for _ in range(CONC)])
        await b.close()
    print('done', n)


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], sys.argv[2]))
