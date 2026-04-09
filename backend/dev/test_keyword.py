import sys, os, json
sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")

from main import keyword_tree_search, load_tree

tree = load_tree()
query = "what are all the courses that satisfy the area B component of the biology major"
results = keyword_tree_search(query, tree)

print("Top keyword matches:")
for r in results[:5]:
    print(f"  Score={r['score']} pages={r['start_index']}-{r['end_index']} title='{r['title']}' matched={r['matched_terms']}")
