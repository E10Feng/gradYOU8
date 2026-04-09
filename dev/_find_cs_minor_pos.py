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
idx = text.find('Minor in Computer Science')
if idx != -1:
    print('Found at', idx, 'of', len(text))
    print(text[idx:idx+1000])
