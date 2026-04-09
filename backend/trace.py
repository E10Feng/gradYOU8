import json

tree_path = r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_arts_sciences.tree.json'
with open(tree_path, encoding='utf-8', errors='replace') as f:
    tree = json.load(f)

structure = tree.get('structure', [])
print('Top-level nodes:', len(structure))
node = structure[0]
print('First node title:', node.get('title', '')[:60])
print('First node num_kids:', len(node.get('nodes', [])))
