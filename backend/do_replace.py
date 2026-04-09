# Read the current main.py
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the start line of tree_retrieve and the start of the next section (# ── Routes)
func_start = None
routes_start = None
for i, line in enumerate(lines):
    if line.startswith('def tree_retrieve('):
        func_start = i
    if func_start is not None and i > func_start and line.startswith('# ── Routes ──'):
        routes_start = i
        break

print(f"tree_retrieve at line {func_start+1}, routes at line {routes_start+1}")
assert func_start is not None and routes_start is not None

new_func = '''def tree_retrieve(query: str, tree: dict, model: str = "MiniMax-M2.7") -> tuple[str, list[dict]]:
    """
    Arts & Sciences tree retrieval:
    1. Ask MiniMax to identify relevant section page ranges from the TOC.
    2. Extract PDF text for those pages and answer.
    """
    from utils import get_text_of_pages

    def build_section_index(nodes, depth=0, lines=None):
        if lines is None:
            lines = []
        for node in nodes:
            title = node.get("title", "")
            start = node.get("start_index", 0)
            end = node.get("end_index", start)
            indent = "  " * depth
            lines.append(f"{indent}[pages {start}-{end}] {title}")
            if node.get("nodes"):
                build_section_index(node["nodes"], depth + 1, lines)
        return lines

    section_index = "\\n".join(build_section_index(tree.get("structure", [])))

    # Step 1: ask MiniMax which page ranges are relevant
    select_prompt = (
        "A student asks: " + query + "\\n\\n"
        "Here is the Arts & Sciences table of contents from the WashU Bulletin:\\n\\n"
        + section_index + "\\n\\n"
        "Which page range(s) are most relevant? Return ONLY valid JSON with key relevant_pages: [{\"start\": N, \"end\": M}]. "
        "If nothing is relevant, return {\"relevant_pages\": []}."
    )

    try:
        raw = call_minimax(model=model, prompt=select_prompt)
        parsed = json.loads(raw) if raw.startswith("{") else {}
    except Exception:
        parsed = {}

    page_ranges = []
    if isinstance(parsed, dict):
        for item in parsed.get("relevant_pages", []):
            start = int(item.get("start", 0))
            end = int(item.get("end", start))
            if start > 0:
                page_ranges.append((start, end))

    # Step 2: extract PDF text for the selected pages
    sources = []
    context_blocks = []
    if page_ranges:
        pdf_path = get_bulletin_pdf()
        for start, end in page_ranges[:4]:
            try:
                text = get_text_of_pages(str(pdf_path), start, end, tag=False)
                if text and len(text.strip()) > 50:
                    snippet = text[:2000]
                    block = "[Pages " + str(start) + "-" + str(end) + "]\n" + snippet
                    context_blocks.append(block)
                    sources.append({
                        "title": "Pages " + str(start) + "-" + str(end),
                        "page_range": str(start) + "-" + str(end),
                        "text": snippet[:500],
                    })
            except Exception:
                pass

    # Step 3: answer from context
    if context_blocks:
        context = "\n\n".join(context_blocks)
        answer_prompt = (
            "You are a WashU degree requirement assistant. A student asks: " + query + "\n\n"
            "Here is relevant content from the WashU Undergraduate Bulletin:\n\n"
            + context + "\n\n"
            "Based ONLY on the content above, answer the student's question. "
            "Be specific with course numbers and unit counts. "
            "If the answer is not in the content, say I couldn't find this information."
        )
        try:
            answer = call_minimax(model=model, prompt=answer_prompt)
            answer = (answer or "").strip()
            if not answer:
                answer = "I couldn't find a confident answer."
        except Exception:
            answer = "I couldn't find a confident answer."
    else:
        answer = "I couldn't find relevant sections in the bulletin for this question."

    return answer, sources

'''

new_lines = lines[:func_start] + [new_func + "\n"] + lines[routes_start:]
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print(f"Done — wrote {len(new_lines)} lines total")
