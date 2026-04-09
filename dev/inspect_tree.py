import json
import sys

tree_path = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\data\bulletin_full.tree.json"
with open(tree_path, 'r', encoding='utf-8') as f:
    tree = json.load(f)

print(f"Total top-level nodes: {len(tree)}")
print()
for i, node in enumerate(tree):
    title = node.get("title", "NO TITLE")
    start = node.get("start_index", "?")
    end = node.get("end_index", "?")
    nodes_count = len(node.get("nodes", []))
    has_text = "text" in node
    print(f"[{i}] {title}")
    print(f"    pages: {start}-{end} | child nodes: {nodes_count} | has_text: {has_text}")
    print()
