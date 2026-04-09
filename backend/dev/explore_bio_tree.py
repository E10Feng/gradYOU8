import sys
import os

backend = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend"
os.chdir(backend)
sys.path.insert(0, ".")

from services.tree_router import get_tree

tree = get_tree("arts_sciences")

def print_tree(nodes, indent=0):
    for node in nodes:
        title = node.get("title", "NO TITLE")
        node_id = node.get("node_id", "?")
        has_text = bool(node.get("text"))
        text_preview = (node.get("text", "")[:100].replace("\n", " ")) if has_text else ""
        child_count = len(node.get("nodes", []))
        print("  " * indent + f"[{node_id}] {title} ({child_count} kids, text_len={len(node.get('text', ''))})")
        if has_text and "biology" in title.lower():
            print("  " * indent + f"  -> TEXT PREVIEW: {text_preview[:200]}")
        if node.get("nodes"):
            print_tree(node["nodes"], indent + 1)

print(f"Doc name: {tree.get('doc_name', 'no name')}")
print(f"Root nodes: {len(tree.get('structure', []))}")
print()

# Find nodes that mention biology in title
def find_bio_nodes(nodes, found=None):
    if found is None:
        found = []
    for node in nodes:
        if "biology" in node.get("title", "").lower():
            found.append(node)
        if node.get("nodes"):
            find_bio_nodes(node["nodes"], found)
    return found

bio_nodes = find_bio_nodes(tree.get("structure", []))
print(f"Nodes with 'biology' in title: {len(bio_nodes)}")
for n in bio_nodes:
    print(f"  [{n.get('node_id', '?')}] {n.get('title', '?')}")

print()
# Also look for "major" in title within arts & sciences
def find_major_nodes(nodes, found=None):
    if found is None:
        found = []
    for node in nodes:
        if "major" in node.get("title", "").lower() or "requirement" in node.get("title", "").lower():
            found.append(node)
        if node.get("nodes"):
            find_major_nodes(node["nodes"], found)
    return found

major_nodes = find_major_nodes(tree.get("structure", []))
print(f"Nodes with 'major' or 'requirement' in title: {len(major_nodes)}")
for n in major_nodes:
    print(f"  [{n.get('node_id', '?')}] {n.get('title', '?')} (kids: {len(n.get('nodes', []))})")
