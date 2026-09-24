"""Scoring helpers: does a fetched site belong to the company, and what does the site say the business does?"""
import re

LEGAL = {'llc', 'inc', 'co', 'corp', 'corporation', 'company', 'ltd', 'lp', 'llp', 'pllc', 'the', 'incorporated', 'pc', 'dba', 'of', 'and'}
GENERIC = {'rentals', 'rental', 'rent', 'rents', 'services', 'service', 'sales', 'equipment', 'equip', 'group', 'enterprises',
           'solutions', 'industries', 'usa', 'america', 'american', 'crane', 'cranes', 'tractor', 'tractors', 'forklift',
           'forklifts', 'truck', 'trucks', 'trailer', 'trailers', 'supply', 'supplies', 'repair', 'machinery', 'machine',
           'construction', 'heavy', 'lift', 'lifts', 'party', 'parts', 'center', 'tool', 'tools', 'portable', 'toilet', 'rigging',
           'farm', 'power', 'industrial', 'material', 'handling', 'aerial', 'inc', 'llc', 'all', 'pro', 'best', 'city', 'new'}

# Heavy-equipment evidence on a site. Weighted: specific machines/brands count more than vague words.
HE_STRONG = [
    r'excavators?', r'mini[- ]?ex', r'skid[- ]?steers?', r'backhoes?', r'bull ?dozers?', r'dozers?', r'wheel loaders?',
    r'track loaders?', r'compact track', r'telehandlers?', r'fork ?lifts?', r'boom lifts?', r'scissor lifts?', r'aerial (work )?platforms?',
    r'man ?lifts?', r'cranes?', r'crane (rental|service)', r'rigging', r'millwright', r'heavy haul', r'lowboys?', r'trenchers?',
    r'compactors?', r'rollers?', r'motor graders?', r'articulated', r'dump trucks?', r'semi[- ]trucks?', r'heavy[- ]duty trucks?',
    r'tractors?', r'implements?', r'combines?', r'balers?', r'hay equipment', r'material handling', r'lift trucks?', r'reach trucks?',
    r'pallet jacks?', r'earth ?moving', r'heavy equipment', r'construction equipment', r'compact equipment', r'ag(ricultural)? equipment',
    r'farm equipment', r'excavation', r'grading', r'site ?work', r'land clearing', r'kubota', r'john deere', r'deere', r'caterpillar',
    r'cat®', r'bobcat', r'case (ce|construction|ih)', r'jcb', r'takeuchi', r'komatsu', r'kobelco', r'volvo ce', r'hitachi', r'develon',
    r'doosan', r'genie', r'jlg', r'skyjack', r'hyster', r'yale', r'toyota (material|forklift)', r'crown (lift|equipment)', r'mahindra',
    r'new holland', r'massey ferguson', r'kioti', r'ls tractor', r'manitou', r'terex', r'grove', r'manitowoc', r'liebherr', r'tadano',
    r'peterbilt', r'kenworth', r'freightliner', r'mack trucks?', r'western star', r'wacker', r'bomag', r'vermeer', r'ditch witch',
    r'generators?', r'air compressors?', r'light towers?', r'dump trailers?', r'equipment trailers?', r'stump grinders?',
]
NO_STRONG = [
    r'bounce ?houses?', r'inflatables?', r'moonwalks?', r'water slides?', r'party rentals?', r'tents?', r'tables? (and|&) chairs?',
    r'linens?', r'weddings?', r'portable (toilets?|restrooms?)', r'porta[- ]?(potty|potties|john)', r'restroom trailers?',
    r'wheelchairs?', r'mobility scooters?', r'stair ?lifts?', r'hospital beds?', r'medical (equipment|supplies)', r'oxygen',
    r'lawn ?mowers?', r'chainsaws?', r'string trimmers?', r'leaf blowers?', r'stihl', r'husqvarna', r'feed (store|and seed)',
    r'pet (food|supplies)', r'dumpsters?', r'roll[- ]?off', r'junk removal', r'plumbing', r'hvac', r'air condition', r'mold',
    r'car rental', r'kayaks?', r'paddle ?boards?', r'jet ?skis?', r'bikes?', r'photo booths?', r'dj services?', r'audio visual',
    r'camera', r'lighting (and|&) grip', r'dance floors?', r'catering', r'cotton candy', r'snow cones?', r'tuxedo', r'costumes?',
    r'real estate', r'apartments?', r'gym', r'fitness', r'dental', r'restaurant', r'pharmacy', r'baby gear', r'strollers?',
]
_c = {}


def _rx(p):
    if p not in _c:
        _c[p] = re.compile(r'\b(?:' + p + r')\b', re.I)
    return _c[p]


def hits(pats, text):
    return [p for p in pats if _rx(p).search(text)]


def name_tokens(name):
    n = name.lower().replace('’', "'")
    n = re.split(r'\s[|–—]\s|\s-\s|\(', n)[0]
    n = n.replace("'s", 's').replace("'", '').replace('&', ' ')
    toks = [t for t in re.findall(r'[a-z0-9]+', n) if t not in LEGAL]
    distinct = [t for t in toks if t not in GENERIC and (len(t) >= 3 or t.isdigit())]
    return toks, distinct


def match_score(name, host, title, desc, site_name, text):
    """0..1: how well the site identifies itself as this company."""
    toks, distinct = name_tokens(name)
    head = ' '.join((title, site_name, desc)).lower()
    body = text.lower()[:6000]
    hostlab = re.sub(r'[^a-z0-9]', '', host.lower().split('.')[0] if not host.startswith('www.') else host.split('.')[1])
    flat_head = re.sub(r'[^a-z0-9]', '', head)
    flat_body = re.sub(r'[^a-z0-9]', '', body)
    full = ''.join(toks)
    if full and len(full) >= 6 and (full in flat_head or full in flat_body[:4000]):
        return 1.0
    key = distinct or toks
    if not key:
        return 0.0
    in_head = sum(1 for t in key if re.search(r'\b' + re.escape(t), head))
    in_body = sum(1 for t in key if re.search(r'\b' + re.escape(t), body))
    in_host = sum(1 for t in key if t in hostlab)
    s = max(in_head / len(key), 0.8 * in_body / len(key), 0.6 * in_host / len(key))
    if not distinct:  # all-generic name ("Aerial Lifts Rental"): weaker evidence
        s *= 0.6
    return round(s, 2)


US_STATE = r'\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b\.?,?\s+\d{5}\b'
US_PHONE = r'\(?\b[2-9]\d{2}\)?[-. ]\d{3}[-. ]\d{4}\b'
NON_US = r'\b(canada|ontario|alberta|british columbia|quebec|manitoba|saskatchewan|nova scotia|mexico|m[eé]xico|india|united kingdom|australia)\b'


def us_signal(text, host):
    if re.search(r'\.(ca|mx|in|uk|au|co\.uk|com\.mx|com\.au)$', host):
        return 'no'
    t = text[:8000]
    us = bool(re.search(US_STATE, t)) or bool(re.search(US_PHONE, t))
    non = len(re.findall(NON_US, t, re.I))
    if us and non < 3:
        return 'yes'
    if non >= 2 and not us:
        return 'no'
    return 'unknown'
