import re

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

NEW_BODY = '''
    import re

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
    heading_list = sorted(all_headings)[:80]
    heading_str = "\n".join("- " + h for h in heading_list)

    select_prompt = (
        "A student asks: " + query + "\n\n"
        "Here are section headings from the WashU Arts & Sciences bulletin:\n\n"
        + heading_str + "\n\n"
        "Which heading(s) are most relevant? Return ONLY valid JSON with key headings: [heading1, ...]. "
        'Return at most 3. If none match, return {"headings": []}.'
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
            context_blocks.append("[" + title + "]\n" + snippet)
            sources.append({"title": title, "page_range": "", "text": snippet[:500]})

    for score, title, text in kw_matches:
        if title not in seen and len(text) > 200 and len(context_blocks) < 4:
            seen.add(title)
            snippet = text[:3000]
            context_blocks.append("[" + title + "]\n" + snippet)
            sources.append({"title": title, "page_range": "", "text": snippet[:500]})

    if not context_blocks:
        return "I couldn't find relevant sections in the bulletin for this question.", []

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

    return answer, sources
'''

# Find tree_retrieve boundaries
m = re.search(r'^def tree_retrieve\(', content, re.MULTILINE)
if not m:
    print("ERROR: tree_retrieve not found")
    exit(1)

func_start = m.start()

# Find the section comment line before tree_retrieve (starts with # and contains a box-drawing char)
line_start = content.rfind('\n', 0, func_start) + 1
section_comment = content[line_start:func_start]

# Find def line
def_end = content.find('\n', func_start)
def_line = content[func_start:def_end + 1]

# Find docstring: first """ after def line, then the next """
first_triple = content.find('"""', def_end)
second_triple = content.find('"""', first_triple + 3)
docstring_end = content.find('\n', second_triple) + 1

print("Section:", repr(section_comment[:40]))
print("Def:", repr(def_line[:60]))
print("Docstring ends at char:", docstring_end)

# New function
new_tree_retrieve = section_comment + def_line + content[def_end+1:docstring_end] + NEW_BODY + '\n'

new_content = content[:line_start] + new_tree_retrieve + content[func_start + len(section_comment):]

with open(r'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\backend\main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Done! New content length:", len(new_content))
