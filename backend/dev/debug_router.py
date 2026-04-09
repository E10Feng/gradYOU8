import sys
sys.path.insert(0, ".")
from services.tree_router import route, get_tree, TREE_META, USE_LLM_ROUTING
from main import tree_retrieve

query = "what are the core classes for the bio major?"

print(f"USE_LLM_ROUTING: {USE_LLM_ROUTING}")
print(f"Query: {query}")
print(f"Route: {route(query)}")
print()

tree_ids = route(query)
for tid in tree_ids:
    print(f"\nLoading tree: {tid}")
    try:
        tree = get_tree(tid)
        print(f"  Tree loaded OK: {tree.get('doc_name', 'no doc_name')}, "
              f"{len(tree.get('structure', []))} structure nodes")
    except Exception as e:
        print(f"  ERROR loading tree: {e}")
        continue

    print(f"  Running tree_retrieve...")
    answer, sources = tree_retrieve(query, tree)
    print(f"  Answer length: {len(answer)}")
    print(f"  Answer: {answer[:300]}...")
    print(f"  Sources: {len(sources)}")
    for s in sources:
        print(f"    - {s['title']}")
