"""Generate likely domains from a company name and keep the ones that resolve in DNS.

usage: python3 candidates.py ids.json out.json   (ids.json: [{id, name}])
out.json: {id: [host, ...]} for hosts that resolve.
"""
import asyncio, json, re, socket, sys

LEGAL = {'llc', 'inc', 'co', 'corp', 'corporation', 'company', 'ltd', 'lp', 'llp', 'pllc', 'the', 'incorporated', 'pc', 'dba'}
GENERIC = {'rentals', 'rental', 'services', 'service', 'sales', 'equipment', 'company', 'and', 'of', 'rent', 'rents',
           'group', 'enterprises', 'solutions', 'industries', 'usa', 'america'}
SWAP = {'rentals': 'rental', 'rental': 'rentals', 'services': 'service', 'service': 'services', 'cranes': 'crane',
        'crane': 'cranes', 'tractors': 'tractor', 'tractor': 'tractors', 'forklifts': 'forklift', 'forklift': 'forklifts',
        'rents': 'rental', 'trucks': 'truck', 'truck': 'trucks', 'equipment': 'equip', 'machinery': 'machine'}


def tokens(name):
    n = name.lower().replace('’', "'")
    n = re.split(r'\s[|–—]\s|\s-\s|\(|,\s*(?=[a-z .]+$)', n)[0]  # drop " | City", " - Location", "(...)"
    n = n.replace("'s", 's').replace("'", '').replace('&', ' and ').replace('+', ' and ')
    toks = re.findall(r'[a-z0-9]+', n)
    return [t for t in toks if t not in LEGAL]


def candidates(name):
    t = tokens(name)
    if not t:
        return []
    base = [t, [x for x in t if x != 'and']]
    if t[-1] in SWAP:
        base.append(t[:-1] + [SWAP[t[-1]]])
        base.append([x for x in t[:-1] if x != 'and'] + [SWAP[t[-1]]])
    core = [x for x in t if x not in GENERIC]
    if core and len(''.join(core)) >= 7 and core != t:
        base.append(core)
    out = []
    for b in base:
        s = ''.join(b)
        if len(s) < 5:
            continue
        out += [s + '.com', s + '.net']
        if len(b) > 1:
            out.append('-'.join(b) + '.com')
    s0 = ''.join(base[1])
    if len(s0) >= 5:
        out += [s0 + 'inc.com', s0 + 'llc.com', s0 + '.us']
    seen, res = set(), []
    for c in out:
        if c not in seen and len(c) <= 67:
            seen.add(c); res.append(c)
    return res[:14]


async def resolves(host, sem):
    loop = asyncio.get_running_loop()
    async with sem:
        try:
            await asyncio.wait_for(loop.getaddrinfo(host, 443, type=socket.SOCK_STREAM), 8)
            return True
        except Exception:
            return False


async def main(src, dst):
    items = json.load(open(src))
    sem = asyncio.Semaphore(200)
    cands = {it['id']: candidates(it['name']) for it in items}
    allh = sorted({h for v in cands.values() for h in v})
    print(len(items), 'companies', len(allh), 'candidate hosts', flush=True)
    ok = await asyncio.gather(*[resolves(h, sem) for h in allh])
    live = {h for h, o in zip(allh, ok) if o}
    print(len(live), 'resolve')
    json.dump({i: [h for h in v if h in live] for i, v in cands.items()}, open(dst, 'w'))


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], sys.argv[2]))
