import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

print('TOP-LEVEL SECTIONS:')
for n in tree:
    print(f"  [{n.get('node_id','?')}] {n['title'][:70]}")

print('\nCOMPUTATIONAL BIOLOGY / GENOMICS NODES:')
for n in flat:
    t = n.get('title','').lower()
    if 'computational' in t or 'genomics' in t or 'bioinform' in t:
        print(f"  [{n.get('node_id','?')}] {n['title'][:70]}")

print('\nCS-RELATED MINOR NODES:')
for n in flat:
    t = n.get('title','').lower()
    if 'computer' in t and ('minor' in t or 'cs' in t.lower()):
        print(f"  [{n.get('node_id','?')}] {n['title'][:70]}")

print('\nBIOLOGY MAJOR OVERVIEW NODES:')
for n in flat:
    t = n.get('title','').lower()
    if 'biology' in t and ('major' in t or 'specialization' in t):
        print(f"  [{n.get('node_id','?')}] {n['title'][:70]}")

print(f'\nTotal nodes: {len(flat)}')
