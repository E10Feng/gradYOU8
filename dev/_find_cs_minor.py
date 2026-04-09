import json, sys
try:
    with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
        tree = json.load(f)
except Exception as e:
    print("Error loading:", e)
    sys.exit(1)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)
print(f"Total nodes: {len(flat)}")

# Search for CS minor in Engineering school nodes
print('ENGINEERING MINORS:')
for n in flat:
    t = n.get('title','')
    nid = n.get('node_id','')
    if nid.startswith('06'):
        if 'minor' in t.lower() or 'computer' in t.lower():
            s = n.get('summary','')
            print(f"\n[{nid}] {t}")
            print(f"  summary: {s[:300]}")

print('\n\nDOUBLE COUNT:')
for n in flat:
    t = n.get('title','').lower()
    s = n.get('summary','').lower()
    if any(w in t for w in ['double', 'overlap', 'shared', 'count toward']):
        print(f"\n  [{n.get('node_id','?')}] {n.get('title','')[:70]}")
