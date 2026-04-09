import json, sys
try:
    with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json', encoding='utf-8') as f:
        tree = json.load(f)
except Exception as e:
    print("Error loading:", e)
    sys.exit(1)

flat = []
def flatten(nodes):
    for n in nodes:
        flat.append(n)
        if n.get('nodes'): flatten(n['nodes'])
flatten(tree)
print(f"Total nodes: {len(flat)}")

# Search in ALL fields for CSE 1301
print('\nCSE 1301 anywhere:')
for n in flat:
    t = n.get('title','')
    s = n.get('summary','')
    txt = n.get('text','')
    combined = (t + s + txt).lower()
    if 'cse 1301' in combined:
        print(f"\n  [{n.get('node_id','?')}] {t[:70]}")
        print(f"  match in: {'title' if 'cse 1301' in t.lower() else 'summary' if 'cse 1301' in s.lower() else 'text'}")

# Search for CS minor
print('\nCS minor anywhere:')
for n in flat:
    t = n.get('title','').lower()
    s = n.get('summary','').lower()
    txt = n.get('text','').lower()
    if 'computer science' in t and 'minor' in t:
        print(f"  [{n.get('node_id','?')}] {n.get('title','')[:70]}")
    elif 'cs minor' in combined or ('computer science' in combined and 'minor' in combined):
        print(f"  [{n.get('node_id','?')}] {n.get('title','')[:70]} (matched in text)")

# Search for double-count in combined text
print('\nDouble count anywhere:')
count = 0
for n in flat:
    t = n.get('title','').lower()
    s = n.get('summary','').lower()
    txt = n.get('text','').lower()
    combined = t + s + txt
    if 'double count' in combined or 'double-count' in combined:
        print(f"  [{n.get('node_id','?')}] {n.get('title','')[:70]}")
        count += 1
print(f"  Total matches: {count}")
