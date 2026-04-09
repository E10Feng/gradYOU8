import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

# Find all nodes under Arts & Sciences section (0184)
# Find CS-related under Arts & Sciences
print('CS NODES UNDER ARTS & SCIENCES (0184):')
for n in flat:
    t = n.get('title','').lower()
    if 'computer' in t or 'cse' in t.lower():
        print(f"  [{n.get('node_id','?')}] {n['title'][:70]}")

print('\nMINOR NODES UNDER ARTS & SCIENCES:')
arts_sciences = next((n for n in tree if n.get('node_id') == '0184'), None)
if arts_sciences and arts_sciences.get('nodes'):
    for n in arts_sciences['nodes']:
        t = n.get('title','').lower()
        if 'minor' in t or 'computer' in t:
            print(f"  [{n.get('node_id','?')}] {n['title'][:70]}")
        # Also check grandchildren
        if n.get('nodes'):
            for nn in n['nodes']:
                tt = nn.get('title','').lower()
                if 'minor' in tt or 'computer' in tt:
                    print(f"    [{nn.get('node_id','?')}] {nn['title'][:70]}")

print('\nDOUBLE COUNT / OVERLAP NODES:')
for n in flat:
    t = n.get('title','').lower()
    s = n.get('summary','').lower()
    if 'double' in t or 'overlap' in t or 'double' in s or 'overlap' in s:
        print(f"  [{n.get('node_id','?')}] {n['title'][:70]}")
        print(f"    summary: {n.get('summary','')[:100]}")
