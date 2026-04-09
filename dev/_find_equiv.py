import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

# Show what CHEM/PHYSICS/MATH requirements appear in node 0252
n = next((x for x in flat if x.get('node_id') == '0252'), None)
if n:
    text = n.get('text', '')
    # Find CHEM mentions
    for kw in ['CHEM', 'Physics', 'PHYS', 'MATH', 'Math']:
        idx = text.find(kw)
        if idx != -1:
            print(f'=== {kw} at {idx} ===')
            print(text[max(0, idx-100):idx+300])
            print()
            break

# Also check if there are equivalency tables anywhere
print('=== Searching all nodes for equivalency tables ===')
for n in flat:
    t = n.get('title', '') + ' ' + n.get('summary', '') + ' ' + n.get('text', '')
    if 'equiv' in t.lower() or 'formerly' in t.lower() or 'formerly known' in t.lower():
        nid = n.get('node_id', '?')
        print(f'[{nid}] {n.get("title","")[:80]}')
        for phrase in ['equiv', 'formerly']:
            idx = t.lower().find(phrase)
            if idx != -1:
                print(t[max(0,idx-100):idx+300])
                break
        print()
