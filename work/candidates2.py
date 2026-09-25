"""Second, wider round of name-based domain guesses for companies still missing a domain."""
import json, re
from candidates import candidates, tokens, GENERIC

TRADE = ['equipment', 'equip', 'crane', 'cranes', 'rental', 'rentals', 'rents', 'tractor', 'tractors', 'forklift',
         'lift', 'machinery', 'truck', 'trucks', 'co', 'inc', 'llc', 'usa', 'group', 'sales', 'services', 'rigging', 'ag']


def candidates2(name):
    t = [x for x in tokens(name) if x != 'the']
    if not t:
        return []
    tried = set(candidates(name))
    full = ''.join(x for x in t if x != 'and')
    core = [x for x in t if x not in GENERIC and x != 'and']
    out = []
    for tld in ('.co', '.biz', '.us', '.org', '.net'):
        out.append(full + tld)
    for suf in ('co', 'usa', 'rents', 'group', 'inc', 'llc', 'online', 'tx', 'ca', 'fl'):
        out.append(full + suf + '.com')
    heads = []
    if core:
        heads.append(core[0])
        if len(core) > 1:
            heads.append(''.join(core[:2]))
    ini = ''.join(x[0] for x in t if x != 'and')
    if len(ini) >= 2:
        heads.append(ini)
    for h in heads:
        for tr in TRADE:
            if tr in t or len(h) + len(tr) < 6:
                continue
            out.append(h + tr + '.com')
    # trade word that appears in the name, e.g. "Hoover Skidsteer Rentals" -> hooverskidsteer.com
    for h in heads:
        for x in t:
            if x not in core and x not in ('and',) and len(h + x) >= 6:
                out.append(h + x + '.com')
    res, seen = [], set()
    for c in out:
        if c not in tried and c not in seen and 6 <= len(c) <= 67:
            seen.add(c); res.append(c)
    return res[:40]


if __name__ == '__main__':
    items = json.load(open('icp_nodomain.json'))
    json.dump([{'id': it['id'], 'name': it['name'], 'c': candidates2(it['name'])} for it in items], open('cand3.json', 'w'))
    print(sum(len(candidates2(it['name'])) for it in items))
    for n in ['Hoover Skidsteer Rentals', 'Richmond Heavy Equipment', 'Lloyd Rosdahl Machinery Riggers, Inc.']:
        print(n, candidates2(n)[:15])
