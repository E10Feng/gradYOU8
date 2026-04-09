import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

# Find 0657 and print its children
n0657 = next((x for x in flat if x.get('node_id')=='0657'), None)
if n0657 and n0657.get('nodes'):
    print('Children of 0657 (Engineering Minors):')
    for child in n0657['nodes']:
        t = child.get('title','')
        nid = child.get('node_id','')
        s = child.get('summary','')[:200]
        print(f'\n  [{nid}] {t}')
        print(f'  {s}')
        # Check if it has CS minor info
        combined = (t + s).lower()
        if 'computer' in combined or 'cs' in combined.lower() or 'cse' in combined.lower():
            print('  *** MATCH ***')

# Also search entire flat for CS minor under 06xx nodes
print('\n\nAll 06xx nodes with CS/computer in title:')
for n in flat:
    nid = n.get('node_id','')
    t = n.get('title','').lower()
    if nid.startswith('06') and ('computer' in t or 'cs minor' in t):
        print(f'  [{nid}] {n.get("title")}')
        print(f'  summary: {n.get("summary","")[:200]}')
