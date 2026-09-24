"""Merge rule-based pass + agent outputs into the final CSV."""
import csv, json, glob, re
recs = json.load(open('recs.json'))
look, rev, name_only = {}, {}, {}
for f in sorted(glob.glob('out/lookup_*.json')):
    for o in json.load(open(f)):
        # agents that ran out of web-search budget wrote name-only placeholders: treat as not researched
        if not re.search(r'budget|not researched|not searched|no search', o.get('note', ''), re.I):
            look[o['id']] = o
        else:
            name_only[o['id']] = o
for f in sorted(glob.glob('out/review_*.json')):
    for o in json.load(open(f)): rev[o['id']] = o
# propagate lookups to duplicate (name, domain) rows
by_key = {}
for r in recs:
    if r['id'] in look: by_key[(r['name'].lower(), r['domain'].lower())] = look[r['id']]

def clean(d):
    d = (d or '').strip().lower()
    d = re.sub(r'^https?://', '', d); d = re.sub(r'^www\.', '', d)
    return d.split('/')[0]

out = []
for r in recs:
    row = dict(company_name=r['name'], original_domain=r['domain'], domain=r['domain'], domain_status='original',
               domain_confidence='', heavy_equipment=r['rule'], category='', qualification_source='name/domain rules',
               us_based='', notes=r['rule_reason'], issue_flagged=r['issue'])
    L = look.get(r['id']) or (by_key.get((r['name'].lower(), r['domain'].lower())) if r['issue'] else None)
    if r['issue']:
        if L:
            row['domain'] = clean(L.get('domain'))
            row['domain_status'] = L.get('status', '')
            row['domain_confidence'] = L.get('confidence', '')
            row['us_based'] = L.get('us_based', '')
            he = L.get('heavy_equipment', '')
            # rules-based "Yes/No" from an unambiguous name stays unless web research disagrees firmly
            if he in ('Yes', 'No') or r['rule'] == 'Review':
                row['heavy_equipment'] = he or 'Unsure'
                row['qualification_source'] = 'web search'
            row['category'] = L.get('category', '')
            row['notes'] = L.get('note', '')
        else:
            row['domain_status'] = 'not_researched'
            if r['rule'] == 'Review' and r['id'] in rev:
                row['heavy_equipment'] = rev[r['id']].get('heavy_equipment', 'Unsure')
            elif r['rule'] == 'Review' and r['id'] in name_only:
                v = name_only[r['id']]
                row.update(heavy_equipment=v.get('heavy_equipment') or 'Unsure', category=v.get('category', ''),
                           qualification_source='AI review (name only)')
            row['notes'] = 'domain not researched (web-search limit reached); ' + row['notes']
    elif r['rule'] == 'Review' and r['id'] in rev:
        v = rev[r['id']]
        row.update(heavy_equipment=v.get('heavy_equipment', 'Unsure'), category=v.get('category', ''),
                   qualification_source='AI review (name/domain)', notes=v.get('note', ''))
    if row['heavy_equipment'] == 'Review':
        row['heavy_equipment'] = 'Unsure'
    out.append(row)
cols = list(out[0])
with open('../heavy_equipment_qualified.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(out)
from collections import Counter
print('heavy_equipment', Counter(o['heavy_equipment'] for o in out))
print('domain_status', Counter(o['domain_status'] for o in out))
print('have domain', sum(1 for o in out if o['domain']), '/', len(out))
