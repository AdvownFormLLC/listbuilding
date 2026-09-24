import csv, re, json
from classify import classify
S='input_heavy_equipment_name_domain.csv'
rows=list(csv.reader(open(S,encoding='utf-8-sig')))[1:]
BAD = re.compile(r'(^|\.)(facebook|fb|instagram|linkedin|yelp|twitter|x|youtube|tiktok|google|goo|googlepages|mapquest|yellowpages|bbb|manta|angi|homeadvisor|thumbtack|nextdoor|houzz|porch|bizapedia|opencorporates|chamberofcommerce|tractorhouse|machinerytrader|equipmenttrader|ironplanet|rbauction|ritchiebros|craigslist|ebay|amazon|linktr|carrd|canva|business|square|wixsite|wix|godaddysites|weebly|ueniweb|hibuwebsites|keeq|base44|wordpress|squarespace|blogspot|site123|webnode|jimdo|strikingly|kabba|tapgoods|pointofrentalcloud|stihldealer|construction-rental|equipmap|manheim|homedepot|lowes|dealerrater|cars|mydealersites)\.[a-z.]+$')
FOREIGN = re.compile(r'\.(ca|mx|in|uk|au|nz|de|fr|es|it|br|ar|co|cl|pe|ph|pk|za|ae|cn|jp|ie|nl|eu)$')
STOP=set('inc llc co corp company the and of a an ltd services service rentals rental rent sales equipment group'.split())
def match(n,d):
    host=re.sub(r'^www\.','',d.lower())
    lab=re.sub(r'[^a-z0-9]','',host)
    toks=re.findall(r'[a-z0-9]+',n.lower().split('|')[0])
    sig=[t for t in toks if t not in STOP and len(t)>=3] or toks
    hit=sum(1 for t in sig if t in lab or (len(t)>=5 and t[:5] in lab))
    ini=''.join(t[0] for t in toks)
    if len(ini)>=2 and ini[:3] in lab: hit+=1
    return hit>0
recs=[]
for i,(n,d) in enumerate(rows):
    d=d.strip(); lab,why=classify(n,d)
    issue=''
    if not d: issue='missing'
    elif d.lower() in ('facebook.com',) or BAD.search(d.lower()): issue='platform/listing domain'
    elif FOREIGN.search(d.lower()) and not d.lower().endswith('.com.co'): issue='non-US domain'
    elif FOREIGN.search(d.lower()): issue='non-US domain'
    elif not match(n,d): issue='domain does not match name'
    recs.append(dict(id=i,name=n.strip(),domain=d,rule=lab,rule_reason=why,issue=issue))
json.dump(recs,open('recs.json','w'))
from collections import Counter
print(Counter(r['issue'] for r in recs))
look=[r for r in recs if r['issue']]
print('lookups',len(look),'unique names',len({r['name'].lower() for r in look}))
rev=[r for r in recs if not r['issue'] and r['rule']=='Review']
print('review-only',len(rev))
