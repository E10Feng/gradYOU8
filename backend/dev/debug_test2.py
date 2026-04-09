import sys, os
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")
sys.path.insert(0, ".")
os.environ["USE_LLM_ROUTING"] = "false"

from services.tree_router import route, get_tree, TREE_META

query = "what are the core classes for the bio major?"

print(f"Query: {query}")

tree_ids = route(query)
print(f"Routed to: {tree_ids}")

for tid in tree_ids:
    try:
        tree = get_tree(tid)
        doc_name = tree.get("doc_name", "NO NAME")
        struct_nodes = len(tree.get("structure", []))
        print(f"  {tid}: doc_name={doc_name}, structure_nodes={struct_nodes}")

        for node in tree.get("structure", [])[:3]:
            title = node.get("title", "NO TITLE")
            text_len = len(node.get("text", ""))
            nodes_count = len(node.get("nodes", []))
            print(f"    Node: {title}, text_len={text_len}, child_nodes={nodes_count}")

    except Exception as e:
        print(f"  {tid}: ERROR {e}")
