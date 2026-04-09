import sys, os

libs_path = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\libs\pageindex_agent"
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")

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

print("Calling ChatGPT_API...")
r = ChatGPT_API(model="MiniMax-M2.7", prompt=prompt)
print("Has <think>:", "<think>" in (r or ""))
print("Has **]:", "**]" in (r or ""))

# Test our stripping
import re
ts = (r or "").replace("<think>", "<<<THINK>>>").replace("</think>", "<<</THINK>>>")
print("\nAfter replacing <think> with marker:")
print(ts[:500])
print("...")
print(ts[-500:])

# Test extract_json on original
print("\n=== extract_json on original ===")
parsed_orig = extract_json(r)
print("Keys:", list(parsed_orig.keys()) if parsed_orig else "None")
print("Answer:", str(parsed_orig.get("answer", ""))[:200] if parsed_orig else "None")

# Test extract_json on thinking_stripped
ts2 = (r or "").replace("<think>", "").replace("</think>", "")
parsed_stripped = extract_json(ts2)
print("\n=== extract_json on thinking-stripped ===")
print("Keys:", list(parsed_stripped.keys()) if parsed_stripped else "None")
print("Answer:", str(parsed_stripped.get("answer", ""))[:200] if parsed_stripped else "None")
