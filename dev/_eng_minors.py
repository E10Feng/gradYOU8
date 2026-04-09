import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

# Find Engineering minors section
for n in flat:
    nid = n.get('node_id','')
    t = n.get('title','')
    s = n.get('summary','').lower()
    if nid.startswith('06'):
        if 'computer science' in t.lower() and 'minor' in t.lower():
            text = n.get('text','')
            print(f'[{nid}] {t}')
            print(s[:300])
            print(text[:3000])
            print()

# Also check 0657 which is Engineering Minors & Departmental Overviews
n = next((x for x in flat if x.get('node_id')=='0657'), None)
if n:
    print(f'=== [0657] {n.get("title")} ===')
    print(n.get('summary','')[:300])
    print()
    # Look for CS minor
    if n.get('nodes'):
        for child in n['nodes']:
            t = child.get('title','')
            if 'computer' in t.lower() or 'cs' in t.lower():
                print(f'  [{child.get("node_id")}] {t}')
                print(child.get('summary','')[:200])
                print()
