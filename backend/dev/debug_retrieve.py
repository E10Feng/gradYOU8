import sys
import os
sys.path.insert(0, ".")
os.environ["USE_LLM_ROUTING"] = "false"
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")

from dotenv import load_dotenv
load_dotenv()

print("MINIMAX_API_KEY set:", bool(os.getenv("MINIMAX_API_KEY")))

# Test tree loading
from services.tree_router import route, get_tree

query = "what are the core classes for the bio major?"

print("Query:", query)
tree_ids = route(query)
print("Routed to:", tree_ids)

# Try loading first tree
if tree_ids:
    tid = tree_ids[0]
    print("Loading tree:", tid)
    try:
        tree = get_tree(tid)
        print("Tree loaded OK:", tree.get("doc_name", "no name"), "nodes:", len(tree.get("structure", [])))
    except Exception as e:
        print("ERROR loading tree:", e)

# Test tree_retrieve
print("\nTesting tree_retrieve...")
from main import tree_retrieve

if tree_ids:
    tid = tree_ids[0]
    tree = get_tree(tid)
    try:
        answer, sources = tree_retrieve(query, tree)
        print("Answer length:", len(answer))
        print("Answer:", answer[:500])
        print("Sources:", len(sources))
        for s in sources[:5]:
            print("  -", s.get("title", "no title"))
    except Exception as e:
        print("ERROR in tree_retrieve:", e)
        import traceback
        traceback.print_exc()
