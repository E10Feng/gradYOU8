import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)
flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)
n = next((x for x in flat if x.get('node_id')=='0649'), None)
text = n.get('text','')
# Find 'Minor in Computer Science'
idx = text.find('Minor in Computer Science')
if idx != -1:
    print(text[idx:idx+2000])
else:
    print('NOT FOUND in node text')
    # Check children
    if n.get('nodes'):
        print('Children:')
        for c in n['nodes']:
            t = c.get('title','')
            nid = c.get('node_id')
            print(' ', nid, '-', t)
            if 'computer science' in t.lower():
                print('FOUND:', c.get('text')[:2000])
