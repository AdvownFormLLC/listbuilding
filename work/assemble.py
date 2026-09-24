"""Join every company with the website evidence gathered, pick the best domain, and pre-score ICP.

Writes evidence.json: one record per input row with the chosen domain, verification level, keyword evidence and a
provisional decision. Rows that need judgement get auto=False and are sent to AI reviewers (review_in/*.json).
"""
import glob, json, os, re

from evidence import HE_STRONG, NO_STRONG, hits, match_score, us_signal

recs = json.load(open('recs.json'))
sites = {}
for f in ('sites2/all.jsonl', 'sites2/cands2.jsonl', 'sites2/empty.jsonl'):
    if os.path.exists(f):
        for l in open(f):
            d = json.loads(l)
            if d.get('captcha'):
                d['cf_challenge'] = True  # SiteGround bot check: site exists but content is hidden
            sites[d['host']] = d  # later files are targeted re-fetches and win
cand_by_name = {}
for cf_, inf_ in (('sites/cands.json', 'cand_in.json'), ('sites/cands2.json', 'cand_in2.json')):
    cands = json.load(open(cf_))
    for it in json.load(open(inf_)):
        cand_by_name[it['name'].lower()] = cands.get(str(it['id']), [])
agent = {}
for f in glob.glob('out/lookup_*.json'):
    for o in json.load(open(f)):
        if not re.search(r'budget|not researched|not searched|no search', o.get('note', ''), re.I):
            agent[o['id']] = o
agent_by_name = {}
for r in recs:
    if r['id'] in agent:
        agent_by_name[r['name'].lower()] = agent[r['id']]

BAD_HOST = re.compile(r'(facebook|instagram|linkedin|yelp|google|mapquest|yellowpages|bbb|manta|angi|homeadvisor|thumbtack|'
                      r'nextdoor|craigslist|ebay|amazon|tractorhouse|machinerytrader|equipmenttrader|ironplanet|homedepot)\.')


def clean(d):
    d = (d or '').strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    return d.split('/')[0]


def final_host(site, host):
    u = site.get('final_url') or ''
    m = re.match(r'https?://([^/]+)', u)
    h = m.group(1).lower() if m else host
    return re.sub(r'^www\.', '', h)


BLOCK_T = re.compile(r'just a moment|attention required|security checkpoint|bot verification|access denied|one moment, please|captcha|forbidden|403', re.I)
DEAD_T = re.compile(r'site not found|setup configuration file|default (web )?(site|server)|coming soon|account suspended|not found|index of /|domain .*expired|hostinger horizons', re.I)


def site_state(s):
    if not s:
        return 'dead'
    if s['parked']:
        return 'parked'
    if s['cf_challenge'] or s.get('captcha') or BLOCK_T.search(s['title'] or '') or s['status'] in (401, 403, 429, 202):
        return 'blocked'
    if s['status'] == 0 or s['status'] >= 404 or DEAD_T.search(s['title'] or ''):
        return 'dead'
    if len(s['text']) < 80 and not s['title']:
        return 'blocked'  # page renders only with JavaScript; site exists
    return 'live'


def evaluate(name, host):
    s = sites.get(host)
    if not s:
        return None
    st = site_state(s)
    ok = st == 'live'
    if ok:
        m = match_score(name, final_host(s, host), s['title'], s['desc'], s.get('site_name', ''), s['text'])
    else:
        m = match_score(name, host, '', '', '', '')  # only the domain label to go on
    return dict(host=host, final=final_host(s, host) if ok else host, ok=ok, state=st, cf=s['cf_challenge'], parked=s['parked'],
                status=s['status'], m=m, site=s)


out = []
for r in recs:
    name, orig = r['name'], clean(r['domain'])
    opts = []
    if orig and orig != 'facebook.com':
        e = evaluate(name, orig)
        if e: e['src'] = 'original'; opts.append(e)
    a = agent.get(r['id']) or agent_by_name.get(name.lower())
    if a and a.get('domain') and clean(a['domain']) != orig:
        e = evaluate(name, clean(a['domain']))
        if e: e['src'] = 'web search'; e['m'] = max(e['m'], 0.7 if a.get('confidence') in ('high', 'medium') else 0.5); opts.append(e)
    for h in cand_by_name.get(name.lower(), []):
        if h == orig:
            continue
        e = evaluate(name, h)
        if e and e['ok']: e['src'] = 'name-based guess, confirmed on site'; opts.append(e)
    opts = [o for o in opts if not BAD_HOST.search(o['final'] + '.')]
    foreign = lambda o: bool(re.search(r'\.(ca|mx|in|uk|au|co\.uk|com\.mx)$', o['final']))

    def rank(o):
        good = {'live': 2, 'blocked': 1}.get(o['state'], 0) if not foreign(o) else 0
        return (good > 0, o['m'] + (0.05 if o['src'] == 'original' else 0) + 0.1 * good)
    opts.sort(key=rank, reverse=True)
    best = opts[0] if opts else None
    rec = dict(id=r['id'], name=name, original_domain=r['domain'], issue=r['issue'], rule=r['rule'])
    if best and best['ok'] and best['m'] >= 0.75 and not foreign(best):
        level = 'verified'
    elif best and best['ok'] and best['m'] >= 0.4 and not foreign(best):
        level = 'check'
    elif best and best['cf'] and best['m'] >= 0.6 and not foreign(best):
        level = 'likely-blocked'
    elif best and best['src'] == 'web search' and not foreign(best):
        level = 'likely-websearch'
    else:
        level = 'none'
    rec['level'] = level
    if best:
        s = best['site']
        blob = ' '.join((s['title'], s['desc'], s['text']))
        rec.update(domain=best['final'], src=best['src'], m=best['m'], state=best['state'], title=s['title'][:120], desc=s['desc'][:200],
                   snippet=s['text'][:350], he=[re.sub(r'\\b|\(|\)|\?|\[|\]', '', h) for h in hits(HE_STRONG, blob)][:10],
                   no=[re.sub(r'\\b|\(|\)|\?|\[|\]', '', h) for h in hits(NO_STRONG, blob)][:8],
                   us=us_signal(s['text'], best['final']) if best['ok'] else ('no' if foreign(best) else 'unknown'),
                   foreign=foreign(best), site_ok=best['ok'],
                   alternatives=[o['final'] for o in opts[1:4]])
    else:
        rec.update(domain='', src='', m=0, state='none', title='', desc='', snippet='', he=[], no=[], us='unknown', foreign=False,
                   site_ok=False, alternatives=[])
    # provisional ICP from site keywords
    he, no = len(rec['he']), len(rec['no'])
    if rec['site_ok'] and level == 'verified' and he >= 3 and no == 0:
        rec['icp'], rec['auto'] = 'Yes', True
    elif rec['site_ok'] and level == 'verified' and no >= 2 and he == 0:
        rec['icp'], rec['auto'] = 'No', True
    else:
        rec['icp'], rec['auto'] = '', False
    out.append(rec)

json.dump(out, open('evidence.json', 'w'))
from collections import Counter
print('level', Counter(o['level'] for o in out))
print('auto', Counter((o['auto'], o['icp']) for o in out))
