import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

# Find PHYSICS 191 and PHYSICS 197 course descriptions
for n in flat:
    nid = n.get('node_id', '')
    title = n.get('title', '')
    text = n.get('text', '')
    if 'PHYSICS 191' in title or 'PHYSICS 197' in title or 'PHYSICS 192' in title or 'PHYSICS 198' in title:
        print(f'=== [{nid}] {title} ===')
        print(text[:500])
        print()

# Also find MATH 309 and MATH 1510
for n in flat:
    nid = n.get('node_id', '')
    title = n.get('title', '')
    if 'MATH 309' in title or 'MATH 1510' in title or 'MATH 2200' in title:
        print(f'=== [{nid}] {title} ===')
        print(n.get('text', '')[:500])
        print()
