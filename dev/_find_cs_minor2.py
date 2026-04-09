import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

# Search all text for 'minor in computer science' or 'CS minor' or 'Computer Science Minor'
for n in flat:
    text = n.get('text','')
    t = text.lower()
    if 'minor in computer science' in t or 'cs minor' in t or 'computer science minor' in t:
        nid = n.get('node_id')
        title = n.get('title')
        print(f'[{nid}] {title}')
        idx_cse = t.find('minor in computer science')
        idx_cs = t.find('cs minor')
        idx_comp = t.find('computer science minor')
        idx = min(i for i in [idx_cse, idx_cs, idx_comp] if i != -1)
        print(text[max(0,idx-100):idx+800])
        print()
