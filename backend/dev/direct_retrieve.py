import sys
import os
sys.path.insert(0, ".")
os.environ["USE_LLM_ROUTING"] = "false"
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")

from dotenv import load_dotenv
load_dotenv()

from services.tree_router import get_tree
from main import tree_retrieve

query = "what are the core classes for the bio major?"

print("Loading arts_sciences tree...")
tree = get_tree("arts_sciences")
print("Tree structure OK:", tree.get("doc_name", "no name"), "root nodes:", len(tree.get("structure", [])))

print("\nRunning tree_retrieve...")
answer, sources = tree_retrieve(query, tree)

print("\nAnswer length:", len(answer))
print("Sources count:", len(sources))

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\direct_retrieve.txt", "w", encoding="utf-8") as f:
    f.write("Answer:\n")
    f.write(answer)
    f.write("\n\nSources:\n")
    for s in sources:
        f.write("  - " + s.get("title", "no title") + "\n")

print("Output written to direct_retrieve.txt")
