"""Build the final researched list: heavy_equipment_researched.csv (+ an ICP-only file)."""
import csv, glob, json, os, re
from collections import Counter

ev = {e['id']: e for e in json.load(open('evidence.json'))}
rev = {}
for f in glob.glob('review2_out/*.json'):
    for o in json.load(open(f)):
        rev[o['id']] = o
srch = {}
for f in glob.glob('search_out/*.json'):
    for o in json.load(open(f)):
        srch[o['name'].lower()] = o


def cat_from(he, no):
    j = ' '.join(he).lower()
    for keys, label in ((('crane', 'rigging', 'millwright', 'heavy haul', 'lowboy'), 'crane / rigging service'),
                        (('fork', 'material handling', 'lift truck', 'reach truck', 'pallet', 'hyster', 'yale', 'toyota'), 'forklift / material handling'),
                        (('boom lift', 'scissor', 'aerial', 'man ?lift', 'genie', 'jlg', 'skyjack', 'telehandler'), 'aerial lift / telehandler'),
                        (('tractor', 'deere', 'kubota', 'implement', 'combine', 'baler', 'hay', 'farm', 'agricultural', 'mahindra', 'new holland', 'massey', 'kioti'), 'ag / tractor equipment dealer'),
                        (('peterbilt', 'kenworth', 'freightliner', 'mack', 'western star', 'semi', 'heavy-duty truck', 'dump truck'), 'heavy truck dealer / service'),
                        (('excavat', 'skid', 'backhoe', 'dozer', 'loader', 'construction equipment', 'compact equipment', 'heavy equipment',
                          'caterpillar', 'cat®', 'bobcat', 'case', 'jcb', 'takeuchi', 'komatsu', 'kobelco', 'develon', 'doosan', 'earth'), 'construction equipment dealer / rental')):
        if any(k.split(' ?')[0] in j for k in keys):
            return label
    n = ' '.join(no).lower()
    for keys, label in ((('bounce', 'inflatable', 'party', 'tent', 'wedding', 'moonwalk', 'water slide', 'tables'), 'party / event rental'),
                        (('toilet', 'porta', 'restroom'), 'portable toilets'),
                        (('wheelchair', 'mobility', 'medical', 'oxygen', 'hospital', 'stair'), 'medical / mobility equipment'),
                        (('mower', 'stihl', 'husqvarna', 'chainsaw', 'trimmer', 'blower'), 'outdoor power equipment'),
                        (('dumpster', 'roll', 'junk'), 'dumpster / waste')):
        if any(k in n for k in keys):
            return label
    return ''


rows = []
for i in sorted(ev):
    e = ev[i]
    o = rev.get(i)
    if o is None:  # auto-decided from strong website evidence
        dom, dstat, icp = e['domain'], 'verified', e['icp']
        cat, us, note = cat_from(e['he'], e['no']), e['us'], f"site: {e['title'][:70]}"
    else:
        dom = re.sub(r'^www\.', '', (o.get('domain') or '').strip().lower())
        dstat = {'wrong': 'no_website'}.get(o['domain_status'], o['domain_status'])
        icp, cat, us, note = o['icp'], o.get('category', ''), o.get('us_based', ''), o.get('note', '')
        if o['domain_status'] == 'wrong':
            note = 'listed domain belongs to another business; ' + note
    s = srch.get(e['name'].lower())
    if not dom and s:
        if s.get('domain'):
            dom, dstat = s['domain'], s.get('domain_status', 'likely')
            note = 'found via web search: ' + s.get('note', '')
        else:
            note = 'web search: ' + s.get('note', 'no own website found')
        if s.get('icp') in ('Yes', 'No') and icp == 'Unsure':
            icp = s['icp']
        cat = cat or s.get('category', '')
    if not dom:
        dstat = 'no_website'
    orig = re.sub(r'^www\.', '', (e['original_domain'] or '').strip().lower())
    if not orig:
        src = 'found' if dom else ''
    elif dom == orig:
        src = 'original (confirmed)' if dstat == 'verified' else 'original'
    elif dom:
        src = 'replaced original'
    else:
        src = 'original removed'
    rows.append({
        'company_name': e['name'],
        'domain': dom,
        'domain_status': dstat,
        'domain_source': src,
        'original_domain': e['original_domain'],
        'heavy_equipment_icp': icp,
        'category': cat,
        'us_based': us if us in ('yes', 'no') else 'unknown',
        'website_title': (e['title'] if dom and dom == e['domain'] else '')[:120],
        'evidence': note,
    })

cols = list(rows[0])
with open('../heavy_equipment_researched.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
icp = [r for r in rows if r['heavy_equipment_icp'] == 'Yes' and r['us_based'] != 'no']
with open('../heavy_equipment_icp_only.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(icp)
print('rows', len(rows), 'icp rows', len(icp))
print('icp', Counter(r['heavy_equipment_icp'] for r in rows))
print('domain_status', Counter(r['domain_status'] for r in rows))
print('source', Counter(r['domain_source'] for r in rows))
print('us', Counter(r['us_based'] for r in rows))
print('ICP Yes by domain_status', Counter(r['domain_status'] for r in icp))
