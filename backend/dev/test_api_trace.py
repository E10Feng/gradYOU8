import sys, os, json

libs_path = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\libs\pageindex_agent"
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

from pageindex_agent.utils import ChatGPT_API, extract_json
from main import load_tree

tree = load_tree()
query = "what are the math requirements for the computational biology major?"

def summarize_tree(nodes, depth=0):
    lines = []
    for node in nodes:
        indent = "  " * depth
        title = node.get("title", "")
        start = node.get("start_index", "?")
        end = node.get("end_index", "?")
        summary = node.get("summary", "")[:100]
        lines.append(f"{indent}- [{start}-{end}] {title} {'| ' + summary if summary else ''}")
        if node.get("nodes"):
            lines.extend(summarize_tree(node["nodes"], depth + 1))
    return lines

tree_overview = "\n".join(summarize_tree(tree.get("structure", [])))

prompt = f"""You are a WashU degree requirement assistant.
A student asks: "{query}"

Here is the document's table of contents with page ranges and summaries:

{tree_overview}

Your task:
1. Identify which section(s) of the table of contents are most relevant to answering this question.
2. Return the page ranges (start_index and end_index) for those sections as JSON.
3. Also return a brief answer to the question based on what you know about the document structure.

Return JSON in this format:
{{
  "relevant_sections": [
    {{"title": "...", "start_index": N, "end_index": M, "reasoning": "..."}},
    ...
  ],
  "answer": "Your brief answer to the question"
}}

Return ONLY JSON, no extra text."""

print("Calling API...")
try:
    r = ChatGPT_API(model="MiniMax-M2.7", prompt=prompt)
    print("Response length:", len(r) if r else 0)
    print("Response[:300]:", r[:300] if r else "None")
except Exception as e:
    print("EXCEPTION:", type(e).__name__, str(e))
    import traceback
    traceback.print_exc()
