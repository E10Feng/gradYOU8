# ── Keyword-based tree search (deterministic fallback) ──────────────────────────
import re


def keyword_tree_search(query: str, tree: dict) -> list[dict]:
    """
    Search the tree for nodes matching key terms from the query.
    Returns top-scoring sections sorted by score descending.
    This is deterministic and avoids LLM routing inconsistency.
    """
    # Normalize query
    q = query.lower()
    # Extract key terms: words 3+ chars, remove stopwords
    stopwords = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can", "has",
        "her", "was", "one", "our", "out", "what", "when", "where", "who",
        "will", "with", "from", "this", "that", "these", "those", "have", "had",
        "they", "them", "their", "would", "could", "should", "which", "your",
        "about", "into", "more", "some", "such", "only", "any", "how", "most",
    }
    terms = [w.strip(".,!?;:()[]{}") for w in q.split() if len(w) >= 3 and w not in stopwords]

    def score_node(node: dict) -> int:
        """Score a node by how many query terms it matches in title + summary."""
        title = (node.get("title") or "").lower()
        summary = (node.get("summary") or "").lower()
        text = title + " " + summary
        score = 0
        for term in terms:
            # Check for whole-word or partial matches
            if re.search(r'\b' + re.escape(term) + r'\b', text):
                score += 2  # whole-word match = 2 pts
            elif term in text:
                score += 1  # partial match = 1 pt
        return score

    def walk(nodes, depth=0):
        results = []
        for node in nodes:
            s = score_node(node)
            if s >= 1:
                results.append((s, depth, node))
            if node.get("nodes"):
                results.extend(walk(node["nodes"], depth + 1))
        return results

    scored = walk(tree.get("structure", []))
    # Sort by score desc, then by depth asc (prefer shallower/more general nodes on tie)
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[:5]

    sections = []
    for score, depth, node in top:
        start = node.get("start_index", 0)
        end = node.get("end_index", start + 1)
        sections.append({
            "title": node.get("title", ""),
            "start_index": start,
            "end_index": end,
            "score": score,
            "matched_terms": [t for t in terms if t in (node.get("title", "") + " " + node.get("summary", "")).lower()],
        })
    return sections


# ── Query (tree-based reasoning retrieval) ───────────────────────────────────
def tree_retrieve(query: str, tree: dict, model: str = "MiniMax-M2.7") -> tuple[str, list[dict]]:
    """
    Given a question and a loaded tree index, find relevant pages and answer.
    Uses a hybrid approach:
      1. Keyword search first (deterministic, consistent)
      2. LLM routing as fallback (for unexpected queries)
    Returns (answer, sources).
    """
    import sys
    from pathlib import Path
    libs_path = Path(__file__).parent / "libs" / "pageindex_agent"
    if str(libs_path) not in sys.path:
        sys.path.insert(0, str(libs_path))
    from pageindex_agent.utils import ChatGPT_API, extract_json

    # ── Step 0: Keyword search (deterministic, always consistent) ─────────────
    sections = keyword_tree_search(query, tree)
    page_texts = []

    if sections and sections[0]["score"] >= 2:
        # High-confidence keyword match — skip LLM routing entirely
        pdf_path = get_bulletin_pdf()
        if pdf_path.exists():
            try:
                from pageindex_agent.utils import get_text_of_pages
                for sec in sections[:3]:
                    start = sec["start_index"]
                    end = sec["end_index"]
                    text = get_text_of_pages(str(pdf_path), start, end + 2, tag=False)
                    text = re.sub(r"(?<=[A-Za-z0-9])\s(?=[A-Za-z0-9])", "", text)
                    text = re.sub(r"([A-Z]{2,})(\d)", r"\1 \2", text)
                    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
                    text = re.sub(r"\s{2,}", " ", text)
                    page_texts.append(f"[Pages {start}-{end}]\n{text}")
            except Exception:
                pass

    # ── Step 1: If no confident keyword match, use LLM routing ───────────────
    if not page_texts:
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

        # Include keyword search hints so LLM can correct itself
        keyword_hints = ""
        if sections:
            top_pages = [f"pages {s['start_index']}-{s['end_index']} ({s['title']})" for s in sections[:3]]
            keyword_hints = f"\n\nPreliminary keyword analysis suggests these sections: {', '.join(top_pages)}. Use these as a guide — verify they are relevant before selecting page ranges."

        prompt = f"""You are a WashU degree requirement assistant.
A student asks: "{query}"
{keyword_hints}

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

CRITICAL: You must respond with ONLY a valid JSON object. Do not include any text before or after the JSON. Start directly with {{ and end directly with }}."""

        response = ChatGPT_API(model=model, prompt=prompt)
        # Strip MiniMax reasoning tags: replace start marker, keep end marker, split on it
        parts = (response or "").replace("<think>", "<<<THINKING>>>", 1).split("</think>")
        post_think = parts[-1].strip() if len(parts) > 1 else (response or "")

        parsed = extract_json(post_think)
        sections = parsed.get("relevant_sections", []) or []
        answer = parsed.get("answer", "") if parsed else ""

        if sections:
            pdf_path = get_bulletin_pdf()
            if pdf_path.exists():
                try:
                    from pageindex_agent.utils import get_text_of_pages
                    for sec in sections[:3]:
                        start = sec.get("start_index", 0)
                        end = sec.get("end_index", start + 1)
                        text = get_text_of_pages(str(pdf_path), start, end + 2, tag=False)
                        text = re.sub(r"(?<=[A-Za-z0-9])\s(?=[A-Za-z0-9])", "", text)
                        text = re.sub(r"([A-Z]{2,})(\d)", r"\1 \2", text)
                        text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
                        text = re.sub(r"\s{2,}", " ", text)
                        page_texts.append(f"[Pages {start}-{end}]\n{text}")
                except Exception:
                    pass

    # ── Step 2: Generate answer from page content ───────────────────────────
    if page_texts:
        content_context = "\n\n".join(page_texts)
        answer_prompt = (
            f"You are a WashU degree requirement assistant. A student asks: {query}\n\n"
            f"Here is the relevant content from the WashU Undergraduate Bulletin:\n\n"
            f"{content_context}\n\n"
            f"Based ONLY on the content above, answer the student's question. "
            f"Be specific with course numbers and unit counts. "
            f"If the answer is not in the content, say I couldn't find this information.\n\n"
            f"IMPORTANT: Write your answer as plain text with markdown formatting where helpful. "
            f"Do NOT return JSON."
        )
        page_response = ChatGPT_API(model=model, prompt=answer_prompt)
        page_parts = (page_response or "").replace("<think>", "<<<THINKING>>>", 1).split("</think>")
        page_answer = page_parts[-1].strip() if len(page_parts) > 1 else (page_response or "")
        if page_answer and not page_answer.startswith("{"):
            answer = page_answer

    # ── Step 3: Fallback if no pages found ─────────────────────────────────
    if not page_texts or not answer:
        if not answer:
            lines = post_think.split("\n") if 'post_think' in dir() else []
            skip_phrases = [
                "based on the content", "i need to", "let me check", "the content says",
                "now produce final answer", "final answer", "thus answer accordingly",
                "the student asks:", "you are a washu", "here is relevant content",
                "return only json", "response:", "answer:",
            ]
            clean_lines = []
            for line in lines:
                stripped = line.strip().lower()
                if any(stripped.startswith(p.lower()) for p in skip_phrases):
                    continue
                if query.lower() in stripped and len(stripped) < len(query) + 30:
                    continue
                clean_lines.append(line)
            answer = "\n".join(clean_lines).strip() or "I couldn't find a confident answer in the document."

    # Normalize Unicode to avoid cp1252 encoding errors on Windows
    import unicodedata
    answer = unicodedata.normalize("NFKC", answer)
    answer = answer.encode("ascii", "ignore").decode("ascii")

    # Build sources
    sources = []
    for sec in (sections or [])[:3]:
        start = sec.get("start_index", 0)
        end = sec.get("end_index", start + 1)
        sources.append({
            "title": sec.get("title", ""),
            "page_range": f"{start}-{end}",
            "text": page_texts[0][:500] + "..." if page_texts else "",
        })

    return answer, sources
