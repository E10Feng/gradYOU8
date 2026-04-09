import json
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
    tree = json.load(f)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)

# Search for PHYSICS 197 in all text
print('PHYSICS 197 mentions:')
for n in flat:
    text = n.get('text', '')
    if 'PHYSICS 197' in text:
        idx = text.find('PHYSICS 197')
        print(f'  [{n.get("node_id")}] {n.get("title","")[:60]}')
        print(text[max(0,idx-50):idx+200])
        print()

print('MATH 1510 mentions:')
for n in flat:
    text = n.get('text', '')
    if 'MATH 1510' in text:
        idx = text.find('MATH 1510')
        print(f'  [{n.get("node_id")}] {n.get("title","")[:60]}')
        print(text[max(0,idx-50):idx+200])
        print()

print('MATH 2200 mentions:')
for n in flat:
    text = n.get('text', '')
    if 'MATH 2200' in text:
        idx = text.find('MATH 2200')
        print(f'  [{n.get("node_id")}] {n.get("title","")[:60]}')
        print(text[max(0,idx-50):idx+200])
        print()

print('PHYSICS 191 mentions:')
for n in flat:
    text = n.get('text', '')
    if 'PHYSICS 191' in text:
        idx = text.find('PHYSICS 191')
        print(f'  [{n.get("node_id")}] {n.get("title","")[:60]}')
        print(text[max(0,idx-50):idx+200])
        print()
