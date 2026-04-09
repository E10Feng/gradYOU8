import sys, os

libs_path = r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend\libs\pageindex_agent"
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

sys.path.insert(0, r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")
os.chdir(r"C:\Users\ethan\.openclaw\workspace\gradYOU8\backend")

from pageindex_agent.utils import ChatGPT_API, extract_json, get_text_of_pages
from main import load_tree, get_bulletin_pdf

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

print("=== TREE OVERVIEW ===")
print(tree_overview[:2000])
print()

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

print("=== STEP 1: Getting page ranges from TOC ===")
r = ChatGPT_API(model="MiniMax-M2.7", prompt=prompt)
print("Response length:", len(r) if r else 0)

# Extract sections
parts = (r or "").replace("<think>", "<<<THINKING>>>", 1).split("</think>")
post_think = parts[-1].strip() if len(parts) > 1 else (r or "")
parsed = extract_json(post_think)
sections = parsed.get("relevant_sections", []) or []
print("Sections found:", sections[:3])
print()

if sections:
    print("=== STEP 2: Reading page content ===")
    pdf_path = get_bulletin_pdf()
    all_text = []
    for sec in sections[:3]:
        start = sec.get("start_index", 0)
        end = sec.get("end_index", start + 1)
        print(f"Reading pages {start}-{end}...")
        text = get_text_of_pages(str(pdf_path), start, end, tag=False)
        print(f"  Got {len(text)} chars")
        all_text.append(f"[Pages {start}-{end}]: {text[:500]}")
    
    print()
    print("=== STEP 3: Generating answer from page content ===")
    content_context = "\n\n".join(all_text)
    answer_prompt = (
        f"You are a WashU degree requirement assistant. A student asks: {query}\n\n"
        f"Here is the relevant content from the WashU Undergraduate Bulletin:\n\n"
        f"{content_context}\n\n"
        f"Based ONLY on the content above, answer the student's question. "
        f"Be specific with course numbers and unit counts. "
        f"If the answer is not in the content, say I couldn't find this information."
    )
    page_response = ChatGPT_API(model="MiniMax-M2.7", prompt=answer_prompt)
    page_parts = (page_response or "").replace("<think>", "<<<THINKING>>>", 1).split("</think>")
    page_answer = page_parts[-1].strip() if len(page_parts) > 1 else (page_response or "")
    print("Page answer:", page_answer[:500])
else:
    print("No sections found!")
