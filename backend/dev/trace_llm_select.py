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
from main import call_minimax

tree = get_tree("arts_sciences")
query = "what are the core classes for the bio major?"

def collect_all_nodes(nodes, collected=None):
    if collected is None:
        collected = []
    for node in nodes:
        collected.append((node.get("title", ""), node))
        if node.get("nodes"):
            collect_all_nodes(node["nodes"], collected)
    return collected

all_nodes = collect_all_nodes(tree.get("structure", []))
query_keywords = [k.lower() for k in query.split() if len(k) > 2]

def title_score(title):
    t = title.lower()
    return sum(1 for kw in query_keywords if kw in t)

scored = [(title_score(t), t, n) for t, n in all_nodes]
scored.sort(key=lambda x: -x[0])

top = scored[:150]
rest = [(t, n) for s, t, n in scored[150:] if s == 0]
sampled_rest = rest[::20]
candidate_titles = sorted(set(t for _, t, _ in top) | set(t for t, _ in sampled_rest))

title_block = "\n".join(f"- {t}" for t in candidate_titles)
select_prompt = (
    "A student asks: " + query + "\n\n"
    "Here are section titles from the WashU bulletin:\n\n"
    + title_block + "\n\n"
    "Which title(s) are most relevant? Return ONLY valid JSON with key 'titles': [title1, title2, ...]. "
    "Return at most 3. If none clearly match, return {'titles': []}."
)

raw = call_minimax(model="MiniMax-M2.7", prompt=select_prompt)

with open(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\dev\llm_raw_response.txt", "w", encoding="utf-8") as f:
    f.write(raw)

print("Raw response written. Length:", len(raw))
print("First 1000 chars:")
print(raw[:1000])
