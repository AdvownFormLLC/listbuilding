import asyncio, json
from dnscheck import resolve_chunk
async def main():
    items = json.load(open('cand3.json'))
    allh = sorted({h for it in items for h in it['c']})
    live = set()
    for i in range(0, len(allh), 500):
        try: r = await resolve_chunk(allh[i:i+500])
        except asyncio.TimeoutError: r = {}
        live |= {h for h, v in r.items() if v}
        if i % 10000 == 0: print(i, len(live), flush=True)
    json.dump(sorted(live), open('sites2/cand3_live.json', 'w'))
    print('done', len(allh), len(live))
asyncio.run(main())
