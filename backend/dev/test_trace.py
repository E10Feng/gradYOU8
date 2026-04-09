import sys, os
sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")
from main import tree_retrieve, load_tree
import json

tree = load_tree()
print("Tree loaded, nodes:", len(tree.get("structure", [])))

query = "what are the math requirements for the computational biology major?"
print("Calling tree_retrieve...")

# Trace the internals
import sys
sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\libs\pageindex_agent")
from pageindex_agent.utils import ChatGPT_API, extract_json

tree2 = load_tree()
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

tree_overview = "\n".join(summarize_tree(tree2.get("structure", [])))

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

print("Calling ChatGPT_API with MiniMax-M2.7...")
response = ChatGPT_API(model="MiniMax-M2.7", prompt=prompt)
print("Response length:", len(response) if response else 0)
print("Response[:500]:" if response else "No response")
if response:
    print(response[:500])
print()
print("Stripping thinking tags...")
response_stripped = response.replace("<think>", "").replace("</think>", "") if response else ""
print("After strip[:500]:")
print(response_stripped[:500])
print()
parsed = extract_json(response_stripped)
print("Parsed keys:", list(parsed.keys()) if parsed else "None")
print("Answer:", str(parsed.get("answer", ""))[:200] if parsed.get("answer") else "NOT FOUND")
