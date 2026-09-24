"""Resolve candidate domains via DNS-over-HTTPS (system resolver is slow on NXDOMAIN here). Resumable."""
import asyncio, json, os, ssl
import aiohttp
from candidates import candidates

DONE = 'sites/dns_done.jsonl'

async def resolve_chunk(hosts):
    ctx = ssl.create_default_context(cafile='/root/.ccr/ca-bundle.crt')
    res = {}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=30, ssl=ctx), trust_env=True) as s:
        async def q(h):
            for ep in ('https://dns.google/resolve', 'https://cloudflare-dns.com/dns-query'):
                try:
                    async with s.get(ep, params={'name': h, 'type': 'A'}, headers={'accept': 'application/dns-json'},
                                     timeout=aiohttp.ClientTimeout(total=10)) as r:
                        d = await r.json(content_type=None)
                        res[h] = d.get('Status') == 0 and any(a.get('type') in (1, 5) for a in d.get('Answer', []))
                        return
                except Exception:
                    continue
        await asyncio.wait_for(asyncio.gather(*[q(h) for h in hosts]), 120)
    return res

async def main():
    items = json.load(open('cand_in.json'))
    cands = {it['id']: candidates(it['name']) for it in items}
    allh = sorted({h for v in cands.values() for h in v})
    known = {}
    if os.path.exists(DONE):
        for l in open(DONE):
            known.update(json.loads(l))
    todo = [h for h in allh if h not in known]
    out = open(DONE, 'a')
    for i in range(0, len(todo), 500):
        try:
            r = await resolve_chunk(todo[i:i + 500])
        except asyncio.TimeoutError:
            r = {}
        known.update(r); out.write(json.dumps(r) + '\n'); out.flush()
        print(i + 500, len(todo), sum(known.values()), flush=True)
    live = {h for h, v in known.items() if v}
    print(len(allh), 'candidates', len(live), 'resolve', len(allh) - len(known), 'unknown')
    json.dump({i: [h for h in v if h in live] for i, v in cands.items()}, open('sites/cands.json', 'w'))

asyncio.run(main())
