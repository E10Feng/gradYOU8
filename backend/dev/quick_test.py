import sys
import os
sys.path.insert(0, ".")
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")

from dotenv import load_dotenv
load_dotenv()

from services.tree_router import route, get_tree
from main import tree_retrieve
import time

query = "what are the core classes for the bio major?"

print("Testing direct retrieval (no API)...")
print(f"Query: {query}")
tree_ids = route(query)
print(f"Routed to: {tree_ids}")

if tree_ids:
    tid = tree_ids[0]
    print(f"Loading {tid}...")
    t0 = time.time()
    tree = get_tree(tid)
    print(f"Loaded in {time.time()-t0:.1f}s")
    print(f"Tree: {tree.get('doc_name', 'no name')}, nodes: {len(tree.get('structure', []))}")
    print(f"Running retrieval...")
    t0 = time.time()
    answer, sources = tree_retrieve(query, tree)
    print(f"Retrieved in {time.time()-t0:.1f}s")
    print(f"Answer length: {len(answer)}")
    print(f"Answer: {answer[:500]}")
    print(f"Sources: {len(sources)}")
