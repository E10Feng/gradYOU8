import sys, os
sys.path.insert(0, ".")
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")

from services.tree_router import route, get_tree, TREE_META

query = "what are the core classes for the bio major?"

print(f"USE_LLM_ROUTING: {os.getenv('USE_LLM_ROUTING', 'not set')}")
print(f"Query: {query}")

tree_ids = route(query)
print(f"Routed to: {tree_ids}")

for tid in tree_ids:
    print(f"\nLoading {tid}...")
    try:
        tree = get_tree(tid)
        print(f"  OK: doc_name={tree.get('doc_name')}, "
              f"structure_nodes={len(tree.get('structure', []))}")

        # Check first few nodes
        for node in tree.get("structure", [])[:3]:
            print(f"  Node: {node.get('title', 'NO TITLE')}, "
                  f"text_len={len(node.get('text', ''))}, "
                  f"nodes={len(node.get('nodes', []))}")

    except Exception as e:
        print(f"  ERROR: {e}")
