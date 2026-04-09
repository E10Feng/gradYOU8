import sys, os
sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")

# Add libs path like main.py now does
libs_path = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\libs\pageindex_agent"
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

from main import tree_retrieve, load_tree
import json

tree = load_tree()
print("Tree nodes:", len(tree.get("structure", [])))

query = "what are the math requirements for the computational biology major?"
print("Calling tree_retrieve...")

try:
    answer, sources = tree_retrieve(query, tree, model="MiniMax-M2.7")
    print("Answer[:300]:", answer[:300] if answer else "None/empty")
    print("Sources:", sources[:1] if sources else "[]")
except Exception as e:
    print("EXCEPTION:", type(e).__name__, str(e))
    import traceback
    traceback.print_exc()
