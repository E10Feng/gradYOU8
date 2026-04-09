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

Return JSON in this format:
{{
  "relevant_sections": [{{"title": "...", "start_index": N, "end_index": M}}],
  "answer": "Brief answer here"
}}

Return ONLY JSON, no extra text."""

print("Calling ChatGPT_API...")
r = ChatGPT_API(model="MiniMax-M2.7", prompt=prompt)
print("Response type:", type(r))
print("Length:", len(r) if r else 0)
if r:
    # Check for thinking tags
    print("Has thinking tags:", "<think>" in r or "</think>" in r)
    print("First 200 chars:", repr(r[:200]))
    print("Last 300 chars:", repr(r[-300:]))
    
    # Try extract_json
    parsed = extract_json(r)
    print("\nParsed keys:", list(parsed.keys()) if parsed else "None/empty")
    print("Parsed answer:", str(parsed.get("answer", ""))[:200] if parsed else "None")
