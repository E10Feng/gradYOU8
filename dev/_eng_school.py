import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

# Find all top-level sections (those that are NOT children of other nodes)
# and find which top-level section contains Engineering
print('TOP-LEVEL NODES:')
for n in tree:
    nid = n.get('node_id','')
    print(f'  [{nid}] {n.get("title")}')

# Find Engineering school
print('\nEngineering school:')
for n in flat:
    t = n.get('title','').lower()
    if 'engineering' in t and ('school' in t or 'program' in t or 'bulletin' in t):
        print(f'  [{n.get("node_id")}] {n.get("title")}')

# Find CSE/CS under engineering
print('\nCSE nodes:')
for n in flat:
    nid = n.get('node_id','')
    t = n.get('title','')
    if nid.startswith('06'):
        if 'computer' in t.lower() or 'cse ' in t.lower():
            print(f'  [{nid}] {t}')
            print(f'    summary: {n.get("summary","")[:200]}')

# Look for CS minor in Engineering
print('\nAll minors in 06xx:')
for n in flat:
    nid = n.get('node_id','')
    t = n.get('title','').lower()
    if nid.startswith('06') and 'minor' in t:
        print(f'  [{nid}] {n.get("title")}')
