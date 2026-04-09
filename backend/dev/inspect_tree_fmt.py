import json

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\data\bulletin_arts_sciences.tree.json", "r", encoding="utf-8") as f:
    tree = json.load(f)

print("Type:", type(tree).__name__)
if isinstance(tree, list):
    print("Length:", len(tree))
    if tree:
        print("First item keys:", list(tree[0].keys()))
        print("First item title:", tree[0].get("title", "NO TITLE"))
elif isinstance(tree, dict):
    print("Keys:", list(tree.keys()))
    if "structure" in tree:
        print("structure is:", type(tree["structure"]).__name__, "length:", len(tree["structure"]))
