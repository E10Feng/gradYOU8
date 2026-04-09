import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)
flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

# Find double-counting / overlap policy
for n in flat:
    text = n.get('text','')
    t = text.lower()
    if ('double' in t and 'count' in t) or ('overlap' in t and ('policy' in t or 'rule' in t)) or 'double-count' in t:
        nid = n.get('node_id')
        title = n.get('title','')
        idx_d = text.lower().find('double')
        idx_o = text.lower().find('overlap')
        idx = min(i for i in [idx_d, idx_o] if i != -1)
        print(nid, '-', title)
        print(text[max(0,idx-100):idx+500])
        print()
