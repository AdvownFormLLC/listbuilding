"""Rule-based first pass: does a company sell, rent, service or otherwise deal with heavy equipment?

Returns ("Yes" | "No" | "Review", reason). "Review" rows go to an AI reviewer.
All patterns are matched at a word start (\b prefix) so "ice" never hits "service".
"""
import re

# Unambiguous heavy-equipment signals; win over any "no" term in the same name.
STRONG_YES = [
    r'cranes?\b', r'fork ?lifts?', r'excavat', r'tractors?\b', r'machinery', r'heavy', r'bob ?cat', r'kubota',
    r'caterpillar', r'cat\b', r'deere', r'komatsu', r'takeuchi', r'kobelco', r'doosan', r'develon', r'jcb\b',
    r'case (ce|construction|ih)\b', r'new holland', r'kioti', r'mahindra', r'massey', r'fendt', r'claas', r'liebherr',
    r'manitou', r'jlg\b', r'skyjack', r'terex', r'hyster', r'gehl', r'volvo (ce|construction)', r'aerial', r'boom (lift|truck)',
    r'scissor', r'man ?lifts?', r'hoists?\b', r'rigg(ing|ers)', r'backhoe', r'loaders?\b', r'dozer', r'bulldozer',
    r'skid ?steer', r'earth ?mov', r'material handling', r'lift trucks?', r'telehandler', r'trencher', r'compactor',
    r'dredg', r'grader', r'mining equip', r'construction equip', r'farm equip', r'ag(ricultural)? equip', r'industrial equip',
    r'compact equip', r'contractors? equip', r'sunbelt rentals', r'united rentals', r'herc rentals', r'h ?& ?e equip',
    r'rdo equip', r'titan machinery', r'ring power', r'implements?\b', r'dump trucks?', r'lowboy', r'heavy haul',
]
# Signals that are good but can be overridden by a "no" context (e.g. "Party Equipment", "Medical Equipment").
WEAK_YES = [
    r'equipment', r'equip\b', r'machines?\b', r'lifts?\b', r'booms?\b', r'ag\b', r'agri', r'farm\b', r'forestry',
    r'logging', r'paving', r'asphalt', r'hydraulic', r'drilling', r'pumps? rental', r'rent[- ]?alls?\b', r'rental (center|centre)',
    r'tool (&|and) equipment', r'equipos', r'maquinaria',
]
NO = [
    r'party', r'parties', r'events?\b', r'bounce', r'bouncy', r'inflatables?', r'jump', r'moonwalk', r'tents?\b', r'wedding',
    r'bridal', r'linens?', r'tables?\b', r'chairs?\b', r'balloons?', r'celebrat', r'photo', r'booth', r'dj\b', r'karaoke',
    r'water slides?', r'slides?\b', r'carnival', r'concession', r'cotton candy', r'snow ?cones?', r'games?\b', r'arcade',
    r'porta', r'potty', r'potties', r'toilets?', r'restrooms?', r'sanitation', r'septic', r'johns?\b', r'medical', r'med\b',
    r'mobility', r'wheelchairs?', r'scooters?', r'oxygen', r'home ?health', r'health', r'hospital', r'pharmacy', r'surgical',
    r'dental', r'cpap', r'respiratory', r'hearing', r'optical', r'mold', r'plumb', r'drains?\b', r'rooter', r'hvac',
    r'heating', r'cooling', r'air condition', r'ac\b', r'appliances?', r'car rentals?', r'auto(motive)?\b', r'cars?\b',
    r'bikes?\b', r'bicycles?', r'e-?bikes?', r'kayaks?', r'canoes?', r'paddle', r'boats?\b', r'marine', r'jet ?skis?',
    r'surf', r'ski\b', r'snowboard', r'golf', r'furniture', r'costumes?', r'audio', r'video', r'av\b', r'sound', r'lighting',
    r'grip\b', r'cameras?', r'film', r'staging', r'stage\b', r'uniforms?', r'lawn', r'mowers?', r'garden', r'feed\b',
    r'seed\b', r'pets?\b', r'fitness', r'gym\b', r'exercise', r'restaurant', r'kitchen', r'food', r'catering', r'salon',
    r'beauty', r'office', r'computers?', r'copiers?', r'printers?', r'music', r'instruments?', r'church', r'schools?',
    r'fenc(e|ing)', r'self storage', r'storage', r'dumpsters?', r'roll ?off', r'junk', r'waste', r'disposal', r'moving',
    r'movers', r'limo', r'bus\b', r'rv\b', r'rvs\b', r'campers?', r'motorcycles?', r'powersports', r'atvs?\b', r'utvs?\b',
    r'golf carts?', r'tux', r'dress', r'baby', r'toys?\b', r'casino', r'pools?\b', r'spas?\b', r'hot tubs?', r'laundry',
    r'cleaning', r'janitorial', r'pest', r'insurance', r'realty', r'real estate', r'bank', r'law\b', r'attorney',
    r'tree (service|care|removal)', r'landscap', r'nursery', r'florist', r'flowers?', r'bakery', r'cafe', r'coffee',
    r'bar\b', r'grill', r'hotel', r'inn\b', r'motel', r'apartments?', r'dance', r'yoga', r'vending', r'hunting', r'fishing',
    r'guns?\b', r'archery', r'outdoors?\b', r'horses?', r'equine', r'saddle', r'tack\b', r'veterinar', r'vet\b', r'grooming',
    r'sleep', r'vision', r'lab\b', r'laborator', r'scientific', r'sports?\b', r'athletic', r'playground', r'play\b',
    r'car ?wash', r'beekeep', r'paint', r'signs?\b', r'screen print', r'embroider', r'trophy', r'printing', r'pressure wash',
    r'windows?\b', r'glass', r'doors?\b', r'garage door', r'solar', r'electrician', r'roofing', r'siding', r'gutters?',
    r'flooring', r'carpet', r'tile', r'cabinets?', r'countertops?', r'handyman', r'towing', r'tow\b', r'wreckers?',
    r'locksmith', r'lock (&|and) key', r'security', r'alarm', r'fire (protection|extinguisher|safety)', r'staffing',
    r'consult', r'marketing', r'software', r'chevrolet', r'chevy', r'ford\b', r'honda', r'nissan', r'hyundai', r'kia\b',
    r'dodge', r'jeep', r'chrysler', r'gmc\b', r'buick', r'subaru', r'mazda', r'lexus', r'bmw', r'mercedes', r'audi\b',
    r'volkswagen', r'tesla', r'toyota\b(?! (material|lift|forklift))', r'porsche', r'carmax', r'dry clean', r'tailor',
    r'jewel', r'pawn', r'thrift', r'consign', r'antique', r'books?\b', r'art\b', r'gallery', r'museum', r'mattress',
    r'vacuum', r'sewing', r'hobby', r'craft', r'magic', r'clown', r'cheese', r'candy', r'livestock feed', r'apparel',
    r'clothing', r'eyewear', r'safeway', r'grocery', r'market\b', r'deli\b', r'pizza', r'tattoo', r'massage', r'chiropract',
    r'therapy', r'rehab', r'clinic', r'home depot', r'lowe\'?s', r'water heater', r'pressure washer', r'small engine',
    r'chainsaws?', r'saws?\b', r'stihl', r'husqvarna', r'outdoor power', r'power equipment', r'water ?sports', r'beach',
    r'umbrella', r'cabana', r'yard (cards?|signs?|greetings?)', r'card my yard', r'lawn (signs?|greetings?)',
]
# Things that could go either way; left for the AI reviewer rather than guessed.
AMBIGUOUS = [
    r'trucks?\b', r'trailers?', r'semi\b', r'freightliner', r'peterbilt', r'kenworth', r'mack\b', r'international',
    r'navistar', r'western star', r'generators?', r'compressors?', r'power systems', r'rent(al)?s?\b', r'leas(e|ing)',
    r'tools?\b', r'hardware', r'suppl(y|ies)', r'parts\b', r'repair', r'services?\b', r'engines?', r'diesel', r'industrial',
    r'construction', r'contractors?', r'excavation', r'site ?work', r'concrete', r'scaffold', r'welding', r'fabricat',
]

_cache = {}


def _find(pats, s):
    for p in pats:
        rx = _cache.get(p)
        if rx is None:
            rx = _cache[p] = re.compile(r'\b(?:' + p + ')')
        if rx.search(s):
            return p
    return None


def _label(p):
    return re.sub(r'\\b|\(\?:|\?|\\', '', p)


def classify(name, domain=''):
    n = name.lower().replace('&amp;', '&').replace('’', "'")
    host = (domain or '').lower()
    strong = _find(STRONG_YES, n)
    if strong:
        return 'Yes', f'name: "{_label(strong)}"'
    no = _find(NO, n)
    weak = _find(WEAK_YES, n)
    if no and weak:
        return 'No', f'name: "{_label(weak)}" qualified by non-heavy term "{_label(no)}"'
    if no:
        return 'No', f'name: non-heavy-equipment term "{_label(no)}"'
    if weak:
        return 'Yes', f'name: "{_label(weak)}"'
    # fall back to the domain label, which often spells out the trade (e.g. "513crane.com")
    label = re.sub(r'^www\.', '', host).split('.')[0]
    for kw in ('crane', 'forklift', 'excavat', 'tractor', 'machinery', 'heavyequip', 'rigging', 'hoist', 'skidsteer',
               'aerial', 'scissorlift', 'boomlift', 'equipment', 'equip'):
        if kw in label:
            return 'Yes', f'domain: "{kw}"'
    for kw in ('party', 'bounce', 'potty', 'toilet', 'medical', 'mobility', 'event', 'plumb', 'mower', 'lawn'):
        if kw in label:
            return 'No', f'domain: "{kw}"'
    amb = _find(AMBIGUOUS, n)
    if amb:
        return 'Review', f'ambiguous term "{_label(amb)}"'
    return 'Review', 'no clear signal in name'
