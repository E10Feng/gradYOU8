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
CRITICAL: You must respond with ONLY a valid JSON object. Do not include any text before or after the JSON. Start directly with {{ and end directly with }}.

Return JSON with the following structure:
{{
  "relevant_sections": [{{"title": "...", "start_index": N, "end_index": M}}],
  "answer": "Brief plain-text answer here"
}}

A student asks: "{query}"

Here is the document's table of contents:
{tree_overview}
"""

print("Calling API...")
r = ChatGPT_API(model="MiniMax-M2.7", prompt=prompt)
print("Response length:", len(r) if r else 0)

# Test the extraction
r_stripped = (r or "").replace("<think>", "").replace("</think>", "")
print("\n=== STRIPPED RESPONSE ===")
print(r_stripped[-1000:])  # Last 1000 chars

# Try standard extract_json
parsed = extract_json(r_stripped)
print("\n=== PARSED (standard) ===")
print("Keys:", list(parsed.keys()) if parsed else "None/empty")
print("Answer:", str(parsed.get("answer", ""))[:200] if parsed else "None")

# Try trailing JSON extraction
import json as _json
last_brace = r_stripped.rfind("}")
print("\n=== TRAILING JSON ATTEMPT ===")
print("last_brace at:", last_brace)
if last_brace > 0:
    cand_start = r_stripped.rfind("{", 0, last_brace)
    print("cand_start:", cand_start)
    if cand_start >= 0:
        candidate = r_stripped[cand_start:last_brace + 1]
        print("Candidate JSON:", candidate[:200])
        if '"answer"' in candidate or "'answer'" in candidate:
            try:
                cp = _json.loads(candidate)
                print("Parsed candidate answer:", str(cp.get("answer", ""))[:200])
            except Exception as e:
                print("JSON parse error:", e)
