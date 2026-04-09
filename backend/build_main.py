import json, os

# Read current main.py to get everything except tree_retrieve body
with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The old tree_retrieve body we want to replace (from "from utils import ChatGPT_API" to "return answer, sources")
old_body = '''    from utils import ChatGPT_API, extract_json

    # Build a concise tree overview for the LLM to reason over
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

    tree_overview = "\\n".join(summarize_tree(tree.get("structure", [])))
    doc_name = tree.get("doc_name", "WashU Bulletin")

    # Prompt the LLM to pick the right pages
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

    response = ChatGPT_API(model=model, prompt=prompt)
    parsed = extract_json(response)

    sections = parsed.get("relevant_sections", [])
    answer = parsed.get("answer", "I couldn't find a confident answer in the document.")

    # Retrieve the actual page text for sources
    sources = []
    if sections:
        pdf_path = get_bulletin_pdf()
        if pdf_path.exists():
            try:
                from utils import get_text_of_pages
                for sec in sections[:3]:  # top 3 only
                    start = sec.get("start_index", 0)
                    end = sec.get("end_index", start + 1)
                    text = get_text_of_pages(str(pdf_path), start, end, tag=False)
                    sources.append({
                        "title": sec.get("title", ""),
                        "page_range": f"{start}-{end}",
                        "text": text[:500] + "..." if len(text) > 500 else text,
                    })
            except Exception:
                pass

    return answer, sources'''

new_body = '''    import re

    def collect_headings(nodes, heading_set=None):
        if heading_set is None:
            heading_set = set()
        for node in nodes:
            text = node.get("text") or ""
            for match in re.finditer(r"(?im)^#{1,6}\\s+([^\\n]+)", text):
                h = match.group(1).strip()
                if len(h) > 4:
                    heading_set.add(h)
            if node.get("nodes"):
                collect_headings(node["nodes"], heading_set)
        return heading_set

    all_headings = collect_headings(tree.get("structure", []))
    heading_list = sorted(all_headings)[:80]
    heading_str = "\\n".join("- " + h for h in heading_list)

    select_prompt = (
        "A student asks: " + query + "\\n\\n"
        "Here are section headings from the WashU Arts & Sciences bulletin:\\n\\n"
        + heading_str + "\\n\\n"
        \'Which heading(s) are most relevant? Return ONLY valid JSON with key "headings": ["heading1", ...]. \'
        \'Return at most 3. If none match, return {"headings": []}.\'
    )

    try:
        raw = call_minimax(model=model, prompt=select_prompt)
        parsed = json.loads(raw) if raw.startswith("{") else {}
    except Exception:
        parsed = {}

    selected = parsed.get("headings", []) if isinstance(parsed, dict) else []

    def find_nodes_by_heading(nodes, targets, results=None):
        if results is None:
            results = []
        for node in nodes:
            text = node.get("text") or ""
            title = node.get("title", "")
            for h in targets:
                if h.lower() in text.lower():
                    results.append((title, text))
                    break
            if node.get("nodes"):
                find_nodes_by_heading(node["nodes"], targets, results)
        return results

    matched = find_nodes_by_heading(tree.get("structure", []), selected)

    keywords = [k.strip() for k in query.split() if len(k.strip()) > 3]
    kw_key = " ".join(keywords[:5])

    def kw_search(nodes, kw_str, results=None):
        if results is None:
            results = []
        for node in nodes:
            text = (node.get("text") or "").lower()
            title = (node.get("title") or "").lower()
            score = sum(1 for kw in kw_str.split() if kw in title or kw in text)
            if score >= 2 and len(node.get("text") or "") > 500:
                results.append((score, node.get("title", ""), node.get("text", "")))
            if node.get("nodes"):
                kw_search(node["nodes"], kw_str, results)
        return results

    kw_matches = kw_search(tree.get("structure", []), kw_key.lower())
    kw_matches.sort(key=lambda x: -x[0])

    context_blocks = []
    sources = []
    seen = set()

    for title, text in matched:
        if title not in seen and len(text) > 200:
            seen.add(title)
            snippet = text[:5000]
            context_blocks.append("[" + title + "]\\n" + snippet)
            sources.append({"title": title, "page_range": "", "text": snippet[:500]})

    for score, title, text in kw_matches:
        if title not in seen and len(text) > 200 and len(context_blocks) < 4:
            seen.add(title)
            snippet = text[:3000]
            context_blocks.append("[" + title + "]\\n" + snippet)
            sources.append({"title": title, "page_range": "", "text": snippet[:500]})

    if not context_blocks:
        return "I couldn\\'t find relevant sections in the bulletin for this question.", []

    context = "\\n\\n".join(context_blocks)

    answer_prompt = (
        "You are a WashU degree requirement assistant. A student asks: " + query + "\\n\\n"
        "Here is relevant content from the WashU Undergraduate Bulletin:\\n\\n"
        + context + "\\n\\n"
        "Based ONLY on the content above, answer the student\\'s question. "
        "Be specific with course numbers and unit counts. "
        "If the answer is not in the content, say I couldn\\'t find this information."
    )

    try:
        answer = call_minimax(model=model, prompt=answer_prompt)
        answer = (answer or "").strip()
        if not answer:
            answer = "I couldn\\'t find a confident answer."
    except Exception:
        answer = "I couldn\\'t find a confident answer."

    return answer, sources'''

if old_body not in content:
    print("ERROR: old_body not found in content!")
    print("Looking for:")
    print(repr(old_body[:200]))
    exit(1)

new_content = content.replace(old_body, new_body)
if new_content == content:
    print("ERROR: no replacement made!")
    exit(1)

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Done!")
