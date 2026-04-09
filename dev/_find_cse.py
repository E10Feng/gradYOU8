import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

# Find CSE 1301 and CSE 2407 course descriptions
print('CSE 1301/2407 related nodes:')
for n in flat:
    t = n.get('title','').lower()
    s = n.get('summary','').lower()
    if 'cse 1301' in t or 'cse 1301' in s or 'cse 2407' in t or 'cse 2407' in s:
        print(f"  [{n.get('node_id','?')}] {n.get('title','')[:70]}")
        print(f"    summary: {n.get('summary','')[:150]}")
