import sys
import os
import re
import json

backend = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend"
sys.path.insert(0, backend)
os.chdir(backend)

from dotenv import load_dotenv
load_dotenv()

from services.tree_router import get_tree

tree = get_tree("arts_sciences")

query = "what are the core classes for the bio major?"

# Step 1: collect headings (exactly as tree_retrieve does)
def collect_headings(nodes, heading_set=None):
    if heading_set is None:
        heading_set = set()
    for node in nodes:
        text = node.get("text") or ""
        for match in re.finditer(r"(?im)^#{1,6} ([^\n]+)", text):
            h = match.group(1).strip()
            if len(h) > 4:
                heading_set.add(h)
        if node.get("nodes"):
            collect_headings(node["nodes"], heading_set)
    return heading_set

all_headings = collect_headings(tree.get("structure", []))
heading_list = sorted(all_headings)
print(f"Total headings collected: {len(heading_list)}")

# Show headings that mention biology
bio_headings = [h for h in heading_list if "biology" in h.lower()]
print(f"\nHeadings mentioning 'biology': {len(bio_headings)}")
for h in bio_headings:
    print(f"  - {h}")

# Show headings that might be the biology major
major_headings = [h for h in heading_list if "major" in h.lower() or "core" in h.lower()]
print(f"\nHeadings mentioning 'major' or 'core': {len(major_headings)}")
for h in major_headings[:20]:
    print(f"  - {h}")
