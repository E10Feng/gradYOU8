import sys
import os
sys.path.insert(0, ".")
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")

from dotenv import load_dotenv
load_dotenv()

from services.tree_router import route, get_tree
from main import tree_retrieve

query = "what are the upper level electives required for the computational biology major?"

print("Query:", query)
print("Routing...")
tree_ids = route(query)
print("Routed to:", tree_ids)

if tree_ids:
    tid = tree_ids[0]
    print("Loading tree:", tid)
    tree = get_tree(tid)
    print("Running retrieval...")
    answer, sources = tree_retrieve(query, tree)
    print("Answer length:", len(answer))
    print("Sources:", len(sources))
    for s in sources:
        print("  -", s.get("title", "no title"))

    with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\direct_test_output.txt", "w", encoding="utf-8") as f:
        f.write("Query: " + query + "\n\n")
        f.write("Routed to: " + str(tree_ids) + "\n\n")
        f.write("Answer:\n")
        f.write(answer)
        f.write("\n\nSources:\n")
        for s in sources:
            f.write("  - " + s.get("title", "no title") + "\n")
    print("Written to direct_test_output.txt")
