"""
PageIndex-style single-shot tree search + MiniMax hybrid retriever.

Replaces the multi-step tool-calling agentic loop with a proven,
simpler pattern from PageIndex's LLM Tree Search tutorial:

  1. LLM router selects relevant split tree(s)
  2. Single-shot LLM call identifies relevant node_ids from the tree structure
  3. Node text is fetched directly from the tree JSON
  4. MiniMax generates the final answer

This dramatically reduces LLM round-trips (from 5-8 to 3) and eliminates
fragile tool-call JSON parsing.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).parent.parent
DATA_DIR = _BACKEND_ROOT.parent / "data"
CHAT_RETRIEVAL_CONFIG = {
    "max_branches": 4,
    "max_nodes": 6,
    "char_budget": 24000,
    "per_node_cap": 8000,
}

SPLIT_TREE_FILES: dict[str, dict[str, str]] = {
    "architecture": {"file": "bulletin_architecture.tree.json", "label": "Architecture"},
    "arts_sciences": {"file": "bulletin_arts_sciences.tree.json", "label": "Arts & Sciences"},
    "engineering": {"file": "bulletin_engineering.tree.json", "label": "Engineering"},
    "art": {"file": "bulletin_art.tree.json", "label": "Art"},
    "university": {"file": "bulletin_university.tree.json", "label": "University"},
    "cross_school": {"file": "bulletin_cross_school.tree.json", "label": "Cross School"},
    "business": {"file": "bulletin_business.tree.json", "label": "Business"},
}


class AgenticTimeoutError(Exception):
    pass


class AgenticToolError(Exception):
    pass


class AgenticParseError(Exception):
    pass


@dataclass
class AgenticResult:
    answer: str
    sources: list[dict]
    diagnostics: dict[str, Any]


# ---------------------------------------------------------------------------
# Tree loading
# ---------------------------------------------------------------------------

def _load_tree_file(path: Path) -> tuple[list[dict], str]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return raw, ""
    if isinstance(raw, dict):
        return raw.get("structure", []), (raw.get("doc_description", "") or "")
    return [], ""


def _tree_summary(structure: list[dict], doc_description: str = "") -> str:
    titles = []
    snippets = []
    for node in structure[:6]:
        t = (node.get("title") or "").strip()
        s = (node.get("summary") or "").strip().replace("\n", " ")
        if t:
            titles.append(t)
        if s:
            snippets.append(s[:140])
    return f"{doc_description} Top sections: {'; '.join(titles[:6])}. {' '.join(snippets[:3])}".strip()


def load_split_tree_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for tree_id, meta in SPLIT_TREE_FILES.items():
        p = DATA_DIR / meta["file"]
        if not p.exists():
            continue
        structure, doc_description = _load_tree_file(p)
        catalog[tree_id] = {
            "tree_id": tree_id,
            "path": p,
            "doc_name": f"WashU Bulletin ({meta['label']})",
            "label": meta["label"],
            "summary": _tree_summary(structure, doc_description),
            "structure": structure,
        }
    return catalog


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_first_json_object(text: str) -> dict:
    start = text.find("{")
    if start == -1:
        raise AgenticParseError("No JSON object in model response")
    depth = 0
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise AgenticParseError("No complete JSON object in model response")
    try:
        return json.loads(text[start:end + 1])
    except Exception as e:
        raise AgenticParseError(f"JSON parse failed: {e}") from e


def _extract_json_array(text: str) -> list:
    """Extract a JSON array from LLM output, handling markdown fences."""
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<thinking[\s\S]*?</thinking>", "", text, flags=re.IGNORECASE)
    start = text.find("[")
    if start == -1:
        obj = _extract_first_json_object(text)
        return obj.get("node_list", obj.get("node_ids", []))
    depth = 0
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise AgenticParseError("No complete JSON array in response")
    try:
        return json.loads(text[start:end + 1])
    except Exception as e:
        raise AgenticParseError(f"JSON array parse failed: {e}") from e


# ---------------------------------------------------------------------------
# Step 1: LLM Router — pick relevant split trees
# ---------------------------------------------------------------------------

def _build_router_prompt(query: str, catalog: dict[str, dict[str, Any]]) -> str:
    lines = []
    for tree_id, entry in catalog.items():
        lines.append(f"- {tree_id}: {entry.get('summary', '')[:200]}")
    ctx = "\n".join(lines)
    return (
        "You are routing a WashU bulletin query to the right tree.\n"
        f"Available tree IDs: {list(catalog.keys())}\n\n"
        f"Query: {query}\n\n"
        f"Trees:\n{ctx}\n\n"
        "Choose 1-2 tree IDs from the list above. "
        "Return ONLY valid JSON with actual tree IDs (not placeholders):\n"
        '{"selected_tree_ids": ["arts_sciences"], "confidence": 0.9}'
    )


def _route_trees_llm(query: str, catalog: dict[str, dict[str, Any]], model: str) -> tuple[list[str], float]:
    from pageindex_agent.utils import ChatGPT_API
    raw = ChatGPT_API(model, _build_router_prompt(query, catalog), stream=False) or ""
    try:
        parsed = _extract_first_json_object(raw)
    except AgenticParseError:
        print(f"[retriever] router parse fail, retrying. sample={raw[:200]!r}")
        retry_prompt = (
            _build_router_prompt(query, catalog)
            + "\n\nIMPORTANT: Output only a single valid JSON object, no explanation."
        )
        raw2 = ChatGPT_API(model, retry_prompt, stream=False) or ""
        parsed = _extract_first_json_object(raw2)
    raw_ids = parsed.get("selected_tree_ids", [])
    selected = [x for x in raw_ids if isinstance(x, str) and x in catalog]
    confidence = float(parsed.get("confidence", 0.0) or 0.0)
    if not selected:
        print(f"[retriever] router returned invalid ids: {raw_ids!r}, valid catalog keys: {list(catalog.keys())}")
        raise AgenticParseError("Router selected no trees")
    return selected[:2], confidence


def route_trees(query: str, catalog: dict[str, dict[str, Any]], model: str) -> list[str]:
    """Route query to relevant trees with deterministic fallback."""
    try:
        selected, confidence = _route_trees_llm(query, catalog, model)
        print(f"[retriever] route llm selected={selected} conf={confidence:.2f}")
        if confidence >= 0.35:
            return selected
    except (AgenticParseError, Exception) as e:
        print(f"[retriever] route llm failed: {e}")

    ql = query.lower()
    is_program_query = any(k in ql for k in ["major", "minor", "requirement", "program", "degree"])
    is_policy_query = any(k in ql for k in ["policy", "pass/fail", "grade", "deadline", "residency", "credit"])

    if is_policy_query:
        fallback_order = ["university", "cross_school", "arts_sciences", "engineering", "business", "architecture", "art"]
    elif is_program_query:
        fallback_order = ["arts_sciences", "engineering", "cross_school", "business", "architecture", "art", "university"]
    else:
        fallback_order = ["arts_sciences", "engineering", "university", "cross_school", "business", "architecture", "art"]

    return [tid for tid in fallback_order if tid in catalog][:3]


# ---------------------------------------------------------------------------
# Step 2: Single-shot LLM tree search (PageIndex pattern)
# ---------------------------------------------------------------------------

def _prepare_tree_for_search(structure: list[dict], max_depth: int = 4) -> str:
    """Format tree as a compact structure with node_ids for the LLM.

    Strips raw text to save context window, keeping only titles, node_ids,
    page ranges, and child counts. Summaries are included only for
    shallow nodes to keep the prompt under ~8K tokens.
    """
    lines = []
    total_chars = 0
    max_chars = 32000

    def walk(nodes: list[dict], depth: int = 0):
        nonlocal total_chars
        if depth > max_depth or total_chars > max_chars:
            return
        indent = "  " * depth
        for node in nodes:
            if total_chars > max_chars:
                return
            nid = node.get("node_id", "")
            title = (node.get("title") or "").replace("&#39;", "'").replace("&amp;", "&")
            start = node.get("start_index", 0)
            end = node.get("end_index", start)
            children = node.get("nodes") or []
            child_count = len(children)

            # Include summaries only for the first 2 levels to save tokens
            if depth <= 1:
                summary = (node.get("summary") or "").strip().replace("\n", " ")[:150]
            else:
                summary = ""

            line = f"{indent}[{nid}] {title} (pages {start}-{end}, {child_count} children)"
            if summary:
                line += f" — {summary}"
            lines.append(line)
            total_chars += len(line)

            if children:
                walk(children, depth + 1)

    walk(structure)
    return "\n".join(lines)


_QUERY_EXPANSIONS = [
    (r"\bcs\b", "computer science"),
    (r"\bcse\b", "computer science"),
    (r"\bbio\b", "biology"),
    (r"\bchem\b", "chemistry"),
    (r"\bphys\b", "physics"),
    (r"\bmath\b", "mathematics"),
    (r"\becon\b", "economics"),
    (r"\bpoli\s*sci\b", "political science"),
    (r"\bpsych\b", "psychology"),
    (r"\banthro\b", "anthropology"),
]


def _expand_query(query: str) -> str:
    """Expand abbreviations in query for better keyword matching."""
    q = query.lower()
    for pattern, replacement in _QUERY_EXPANSIONS:
        q = re.sub(pattern, replacement, q)
    return q


def _infer_program_focus(query: str, model: str = "MiniMax-M2.7") -> dict:
    """
    Identify the exact program target from a natural-language question.
    Returns a dict with keys: program_name, program_type, retrieval_query.
    """
    q = (query or "").strip()
    if not q:
        return {}

    from pageindex_agent.utils import ChatGPT_API

    prompt = (
        "Extract the target WashU program from the student question.\n"
        "Return ONLY JSON with keys:\n"
        '{"program_name":"", "program_type":"major|minor|", "retrieval_query":""}\n'
        "Rules:\n"
        "- If the question asks about a minor, program_type must be 'minor'.\n"
        "- If the question asks about a major, program_type must be 'major'.\n"
        "- IMPORTANT: The word 'major' in phrases like 'major requirements' or "
        "'key requirements' is an ADJECTIVE, not a program type. Only set "
        "program_type='major' when it identifies a degree program "
        "(e.g. 'biology major', 'the major in computer science').\n"
        "- retrieval_query must be short and requirement-focused:\n"
        "  'what are the requirements for the <program_name> <program_type>'\n"
        "- If unknown, return empty strings.\n\n"
        f"Question: {q}"
    )
    try:
        raw = ChatGPT_API(model, prompt, stream=False) or ""
        raw = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"<thinking[\s\S]*?</thinking>", "", raw, flags=re.IGNORECASE)
        parsed = _extract_first_json_object(raw)
        if not isinstance(parsed, dict):
            return {}
        pname = str(parsed.get("program_name", "") or "").strip()
        ptype = str(parsed.get("program_type", "") or "").strip().lower()
        rq = str(parsed.get("retrieval_query", "") or "").strip()
        if ptype not in {"major", "minor"}:
            ptype = ""
        return {"program_name": pname, "program_type": ptype, "retrieval_query": rq}
    except Exception:
        return {}


def _derive_retrieval_query(
    query: str,
    model: str = "MiniMax-M2.7",
    focus: dict | None = None,
) -> str:
    """
    Dedicated prompt-scanner step (separate LLM call) that returns a focused
    retrieval query. Falls back to original query if scanner output is empty.

    Pass `focus` from a prior `_infer_program_focus` call to avoid a second
    redundant scanner LLM call (which can return inconsistent results).
    """
    q = (query or "").strip()
    if not q:
        return q

    f = focus if isinstance(focus, dict) else _infer_program_focus(q, model=model)
    rq = (f.get("retrieval_query", "") if isinstance(f, dict) else "") or ""
    if rq:
        return rq

    return q


def _exact_requirements_query(focus: dict, fallback_query: str) -> str:
    """Force exact query shape: requirements for <program> <major/minor>."""
    if not isinstance(focus, dict):
        return fallback_query
    program_name = str(focus.get("program_name", "") or "").strip()
    program_type = str(focus.get("program_type", "") or "").strip().lower()
    if program_name and program_type in {"major", "minor"}:
        # Don't append program_type if program_name already ends with it —
        # avoids "...biology major major" when the LLM includes the type in the name.
        name_tail = program_name.lower().rstrip(". ")
        if name_tail.endswith(program_type) or name_tail.endswith(", b.a") or name_tail.endswith(", b.s"):
            return f"what are the requirements for the {program_name}"
        return f"what are the requirements for the {program_name} {program_type}"
    return fallback_query


def _query_terms(query: str) -> tuple[list[str], list[str]]:
    expanded = _expand_query(query)
    stopwords = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can", "has",
        "what", "when", "where", "who", "how", "which", "this", "that", "with",
        "from", "about", "into", "have", "does", "tell", "list", "show", "need",
    }
    words = re.findall(r"[a-z]+", expanded)
    terms = [w for w in words if w not in stopwords and len(w) >= 3]
    type_words = list({w for w in words if w in {"major", "minor", "specialization"}})
    return terms, type_words


def _score_node(node: dict, terms: list[str], type_words: list[str]) -> int:
    title = (node.get("title") or "").lower()
    summary = (node.get("summary") or "").lower()
    full_text = (node.get("text") or "").lower()
    text_sample = full_text[:6000]
    blob = title + " " + summary + " " + text_sample

    score = 0
    for t in terms:
        if t in title:
            score += 4
        elif t in summary:
            score += 2
        elif t in text_sample:
            score += 1
    for tw in type_words:
        if tw in blob:
            score += 3

    # Bonus: exact subject+type phrase appears in full text.
    subject_terms = [t for t in terms if t not in type_words]
    for tw in type_words:
        phrase = " ".join(subject_terms + [tw])
        if len(phrase) > 4 and phrase in full_text:
            score += 10
            break
    return score


def _walk_descendants(node: dict) -> list[dict]:
    out: list[dict] = []

    def walk(cur: dict):
        out.append(cur)
        for child in cur.get("nodes") or []:
            walk(child)

    walk(node)
    return out


def _pick_hierarchical_nodes(
    catalog: dict[str, dict[str, Any]],
    query: str,
    max_branches: int = 4,
    max_nodes: int = 6,
) -> tuple[list[tuple[int, str, dict]], list[dict]]:
    """
    Two-step hierarchical retrieval:
      1) Pick top branches (non-leaf nodes) across split trees.
      2) Pick best leaves from those branches.
    """
    terms, type_words = _query_terms(query)
    if not terms:
        return [], []

    branch_candidates: list[tuple[int, str, dict, str]] = []
    for tree_id, entry in catalog.items():
        structure = entry.get("structure") or []
        for root in structure:
            first_level = root.get("nodes") or []
            if not first_level:
                # Handle trees that are already flat.
                score = _score_node(root, terms, type_words)
                if score >= 3:
                    branch_candidates.append((score, tree_id, root, root.get("title", "")))
                continue
            for child in first_level:
                # Branch score is based on BOTH branch metadata and best descendant leaf.
                direct_score = _score_node(child, terms, type_words)
                best_leaf_score = 0
                for d in _walk_descendants(child):
                    if d.get("nodes"):
                        continue
                    best_leaf_score = max(best_leaf_score, _score_node(d, terms, type_words))
                score = max(direct_score, best_leaf_score)
                title_l = (child.get("title") or "").lower()
                if "(directory)" in title_l or title_l.strip() == "index":
                    score -= 2
                if score >= 3:
                    branch_candidates.append((score, tree_id, child, child.get("title", "")))

    branch_candidates.sort(key=lambda x: x[0], reverse=True)
    chosen_branches = branch_candidates[:max_branches]

    leaf_candidates: list[tuple[int, str, dict]] = []
    diag_branches: list[dict] = []
    for bscore, tree_id, branch, title in chosen_branches:
        descendants = _walk_descendants(branch)
        local_count = 0
        for node in descendants:
            children = node.get("nodes") or []
            if children:
                continue
            score = _score_node(node, terms, type_words)
            if score >= 3:
                # Mild boost for nodes directly under the chosen branch.
                score += 2 if node in (branch.get("nodes") or []) else 0
                leaf_candidates.append((score, tree_id, node))
                local_count += 1
        diag_branches.append({
            "tree_id": tree_id,
            "branch_title": title,
            "branch_score": bscore,
            "leaf_hits": local_count,
        })

    leaf_candidates.sort(key=lambda x: x[0], reverse=True)

    # Deduplicate by node_id while preserving score order.
    deduped: list[tuple[int, str, dict]] = []
    seen_ids: set[str] = set()
    for score, tree_id, node in leaf_candidates:
        nid = str(node.get("node_id") or "")
        if not nid or nid in seen_ids:
            continue
        seen_ids.add(nid)
        deduped.append((score, tree_id, node))
        if len(deduped) >= max_nodes:
            break

    return deduped, diag_branches


def _keyword_candidates(structure: list[dict], query: str, max_results: int = 12) -> list[dict]:
    """Fast keyword search over node titles, summaries, and text to find candidates.

    This is the "value function" in PageIndex's hybrid search — instant,
    no LLM calls required. Returns scored candidate nodes.
    """
    terms, type_words = _query_terms(query)

    if not terms:
        return []

    candidates: list[tuple[int, dict]] = []

    def walk(nodes: list[dict]):
        for node in nodes:
            score = _score_node(node, terms, type_words)

            if score >= 3:
                node["_kw_score"] = score
                candidates.append((score, node))

            children = node.get("nodes") or []
            if children:
                walk(children)

    walk(structure)
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [node for _, node in candidates[:max_results]]


def _llm_select_from_candidates(
    query: str,
    candidates: list[dict],
    model: str,
) -> list[str]:
    """LLM picks the most relevant nodes from keyword-filtered candidates.

    Much faster than searching the entire tree — candidates list is small.
    """
    from pageindex_agent.utils import ChatGPT_API

    # Build compact candidate list for the LLM
    items = []
    for node in candidates:
        nid = node.get("node_id", "")
        title = (node.get("title") or "").replace("&#39;", "'").replace("&amp;", "&")
        start = node.get("start_index", 0)
        end = node.get("end_index", start)
        summary = (node.get("summary") or "").strip().replace("\n", " ")[:150]
        text_preview = (node.get("text") or "").strip()[:200].replace("\n", " ")
        items.append(
            f"[{nid}] {title} (pages {start}-{end})\n"
            f"  Summary: {summary}\n"
            f"  Preview: {text_preview}"
        )

    candidates_text = "\n\n".join(items)

    prompt = f"""Select the nodes most likely to answer this question about the WashU bulletin.

Question: {query}

Candidate nodes:
{candidates_text}

Select 2-5 node IDs that best answer the question. Prefer nodes with specific program requirements over general overviews.

Reply ONLY with JSON: {{"node_list": ["node_id1", "node_id2"]}}"""

    raw = ChatGPT_API(model, prompt, stream=False) or ""
    raw = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<thinking[\s\S]*?</thinking>", "", raw, flags=re.IGNORECASE)

    try:
        parsed = _extract_first_json_object(raw)
        ids = parsed.get("node_list", parsed.get("node_ids", []))
        if isinstance(ids, list):
            return [str(nid) for nid in ids if nid]
    except AgenticParseError:
        pass

    # Fallback: return top candidates by score
    return [n.get("node_id", "") for n in candidates[:4] if n.get("node_id")]


def _hybrid_search(query: str, structure: list[dict], model: str) -> list[str]:
    """PageIndex-style hybrid search: keyword pre-filter + LLM selection.

    1. Instant keyword search finds candidate nodes
    2. LLM selects the most relevant from candidates
    """
    candidates = _keyword_candidates(structure, query)
    print(f"[retriever] keyword_candidates={len(candidates)} titles={[c.get('title','')[:40] for c in candidates[:5]]}")

    if not candidates:
        return []

    if len(candidates) <= 4:
        return [n.get("node_id", "") for n in candidates if n.get("node_id")]

    return _llm_select_from_candidates(query, candidates, model)


# ---------------------------------------------------------------------------
# Step 3: Fetch node text by node_id
# ---------------------------------------------------------------------------

def _find_nodes_by_ids(structure: list[dict], target_ids: set[str]) -> list[dict]:
    """Walk the tree and collect nodes whose node_id is in target_ids."""
    found: list[dict] = []

    def walk(nodes: list[dict]):
        for node in nodes:
            nid = node.get("node_id", "")
            if nid in target_ids:
                found.append(node)
            children = node.get("nodes") or []
            if children:
                walk(children)

    walk(structure)
    return found


def _get_node_text(node: dict) -> str:
    """Extract text content from a node, falling back to PDF if needed."""
    text = (node.get("text") or "").strip()
    if text:
        return text

    start = node.get("start_index", 0)
    end = node.get("end_index", start)
    try:
        from pageindex_agent.utils import get_text_of_pages
        pdf_path = DATA_DIR / "bulletin_full.pdf"
        if pdf_path.exists():
            return get_text_of_pages(str(pdf_path), start, end + 1, tag=False)
    except Exception:
        pass
    return ""


def _fetch_evidence(structure: list[dict], node_ids: list[str]) -> tuple[str, list[dict]]:
    """Fetch text for the given node_ids and return (combined_text, sources)."""
    target_set = set(node_ids)
    nodes = _find_nodes_by_ids(structure, target_set)

    texts: list[str] = []
    sources: list[dict] = []
    char_budget = 24000

    for node in nodes:
        if sum(len(t) for t in texts) >= char_budget:
            break
        text = _get_node_text(node)
        if not text:
            continue
        title = (node.get("title") or "").replace("&#39;", "'").replace("&amp;", "&")
        start = node.get("start_index", 0)
        end = node.get("end_index", start)

        remain = char_budget - sum(len(t) for t in texts)
        node_text = text[:min(remain, 8000)]
        texts.append(f"[{title}, pages {start}-{end}]\n{node_text}")
        sources.append({
            "title": title,
            "page_range": f"{start}-{end}",
            "tree_id": "",
        })

    return "\n\n".join(texts), sources


# ---------------------------------------------------------------------------
# Step 4: Answer generation
# ---------------------------------------------------------------------------

def _generate_answer(query: str, evidence_text: str, model: str) -> str:
    """Generate a final answer from the fetched evidence.

    Handles both plain queries and queries with [STUDENT CONTEXT] blocks.
    Directly answers the user's question without an intermediate requirements-dump step.
    """
    if not evidence_text.strip():
        return "I couldn't find specific information about that in the WashU Undergraduate Bulletin."

    from pageindex_agent.utils import ChatGPT_API

    query_l = (query or "").lower()
    disambiguation = (
        "Program disambiguation rules:\n"
        "- Use requirements only for the exact program type asked (major vs minor).\n"
        "- If evidence includes similarly named programs, ignore non-matching programs.\n"
        "- Do not merge requirements across different programs.\n"
    )
    if "computer science" in query_l and "minor" in query_l:
        disambiguation += (
            "- For Computer Science minor questions, IGNORE requirements for "
            "'Second Major in Computer Science + Mathematics' and any major-only tracks.\n"
            "- Prefer the 5-course CS minor table when present.\n"
        )

    student_ctx_note = ""
    if "[STUDENT CONTEXT]" in query:
        student_ctx_note = (
            "If the student listed completed courses, compare them against the bulletin requirements "
            "and state exactly what is still needed. Use concise bullets with course codes and counts.\n"
        )

    prompt = (
        "You are a WashU degree planning assistant. Answer based ONLY on the provided bulletin content below.\n"
        "Be specific with course numbers and unit counts. "
        "If the answer is not in the content, say you could not find it.\n"
        "Do not infer that a program does not exist unless the provided content explicitly states that.\n\n"
        f"{disambiguation}"
        f"{student_ctx_note}\n"
        f'Student question: "{query}"\n\n'
        f"Bulletin content:\n{evidence_text[:18000]}\n\n"
        "Answer:"
    )

    try:
        response = ChatGPT_API(model, prompt, stream=False) or ""
        response = re.sub(r"<thinking[\s\S]*?</thinking>", "", response, flags=re.IGNORECASE)
        response = re.sub(r"<think>[\s\S]*?</think>", "", response, flags=re.IGNORECASE)
        response = re.sub(r"\[/?INST\]", "", response, flags=re.IGNORECASE)
        return response.strip()
    except Exception:
        return "I had trouble generating an answer. Please try rephrasing your question."


def _compare_requirements_to_user_query(original_query: str, requirements_answer: str, model: str) -> str:
    """Third LLM call: use requirements output to answer the original user question."""
    from pageindex_agent.utils import ChatGPT_API

    req_l = (requirements_answer or "").lower()
    strict_rules = (
        "Critical grounding rules:\n"
        "- Treat the requirements lookup result as the ONLY source of truth.\n"
        "- Do NOT add requirements that are not explicitly present in that result.\n"
        "- Do NOT import rules from similarly named programs (e.g., second major tracks).\n"
        "- If the lookup result already lists course codes and units, do NOT say the requirements "
        "are missing or not in the excerpt.\n"
    )
    if (
        "minor in computer science" in req_l
        or "computer science minor" in req_l
    ) and "five" in req_l and "core" in req_l and "elective" in req_l:
        strict_rules += (
            "- The lookup result defines CS minor as exactly five courses (4 core + 1 elective).\n"
            "- Therefore, do NOT mention any 4000-level minimum unless it appears explicitly in the lookup result.\n"
        )

    prompt = (
        "You are a WashU degree planning assistant.\n"
        "Use only the requirements lookup result below and the original user question.\n"
        "If the user listed completed courses, compare them against requirements and say exactly what is still needed.\n"
        "Use concise bullets with course codes and counts.\n"
        "If requirements are incomplete in the lookup result, state that clearly.\n\n"
        f"{strict_rules}\n"
        f"Original user question:\n{original_query}\n\n"
        f"Requirements lookup result:\n{requirements_answer[:12000]}\n\n"
        "Helpful answer:"
    )
    try:
        response = ChatGPT_API(model, prompt, stream=False) or ""
        response = re.sub(r"<thinking[\s\S]*?</thinking>", "", response, flags=re.IGNORECASE)
        response = re.sub(r"<think>[\s\S]*?</think>", "", response, flags=re.IGNORECASE)
        response = re.sub(r"\[/?INST\]", "", response, flags=re.IGNORECASE)
        cleaned = response.strip()
        return cleaned if cleaned else requirements_answer
    except Exception:
        return requirements_answer


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def _gather_tree_evidence(
    catalog: dict[str, Any],
    query: str,
    *,
    max_branches: int = 4,
    max_nodes: int = 6,
    char_budget: int = 24000,
    per_node_cap: int = 8000,
) -> tuple[str, list[dict], list[dict], dict[str, Any]]:
    """
    Hierarchical node pick + text assembly. Kept in sync with chat (agentic_retrieve)
    so audit/requirements extraction sees the same evidence shape and budgets.
    """
    top, branch_diag = _pick_hierarchical_nodes(catalog, query, max_branches=max_branches, max_nodes=max_nodes)

    all_texts: list[str] = []
    all_sources: list[dict] = []
    search_diag = [{"score": s, "tree_id": tid, "title": (c.get("title") or "")[:50]} for s, tid, c in top]

    for _score, tree_id, node in top:
        if sum(len(t) for t in all_texts) >= char_budget:
            break
        text = _get_node_text(node)
        if not text:
            continue
        title = (node.get("title") or "").replace("&#39;", "'").replace("&amp;", "&")
        start = node.get("start_index", 0)
        end = node.get("end_index", start)
        remain = char_budget - sum(len(t) for t in all_texts)
        node_text = text[: min(remain, per_node_cap)]
        all_texts.append(f"[{title}, pages {start}-{end}]\n{node_text}")
        all_sources.append({
            "title": title,
            "page_range": f"{start}-{end}",
            "tree_id": tree_id,
        })

    combined = "\n\n---\n\n".join(all_texts)
    return combined, all_sources, search_diag, branch_diag


def _merge_gather_evidence(
    primary: tuple[str, list[dict], list[dict], list[dict]],
    secondary: tuple[str, list[dict], list[dict], list[dict]],
    char_budget: int,
) -> tuple[str, list[dict], list[dict], list[dict]]:
    """Concatenate two gather results up to char_budget; dedupe sources by title+page."""
    ev1, src1, sd1, bd1 = primary
    ev2, src2, sd2, bd2 = secondary
    merged = (ev1.strip() + "\n\n---\n\n" + ev2.strip()).strip() if ev1.strip() and ev2.strip() else (ev2 or ev1)
    if len(merged) > char_budget:
        merged = merged[:char_budget]
    seen: set[tuple[str, str]] = set()
    out_src: list[dict] = []
    for s in src1 + src2:
        key = (s.get("title", ""), s.get("page_range", ""))
        if key in seen:
            continue
        seen.add(key)
        out_src.append(s)
    merged_branches = list(bd1) + list(bd2)
    return merged, out_src, sd1 + sd2, merged_branches


def agentic_retrieve(query: str, profile: dict | None = None, model: str = "MiniMax-M2.7") -> AgenticResult:
    """
    3-step retrieval pipeline adopting PageIndex's hybrid search pattern:
      Step 1 (LLM): Identify which major/minor the query is about.
      Step 2 (LLM x2): Route to relevant split tree(s), then hybrid search
                        (keyword candidates → LLM node selection) within those trees.
      Step 3 (LLM): Generate a direct answer from the fetched evidence.
    """
    start_time = time.time()

    # ------------------------------------------------------------------
    # Step 1 — Identify the program the user is asking about
    # ------------------------------------------------------------------
    print("[retriever] step1: identifying program focus")
    scanner = _infer_program_focus(query, model=model)
    program_name = str(scanner.get("program_name", "") or "").strip()
    program_type = str(scanner.get("program_type", "") or "").strip().lower()

    if program_name and program_type in {"major", "minor"}:
        retrieval_query = f"what are the requirements for the {program_name} {program_type}"
    else:
        retrieval_query = query  # fall back to original for general questions

    print(f"[retriever] step1 done: program={program_name!r} type={program_type!r} retrieval_query={retrieval_query!r}")

    # Augment the answer query with student context when available
    answer_query = query
    if profile:
        student = profile.get("student", {})
        programs = profile.get("programs", [])
        answer_query = (
            f"{query}\n\n[STUDENT CONTEXT]\n"
            f"Student: {student.get('name', 'Unknown')}\n"
            f"Programs: {', '.join([p.get('name', '') for p in programs])}\n"
            f"[/STUDENT CONTEXT]"
        )

    # ------------------------------------------------------------------
    # Step 2 — Route to relevant trees, then hybrid search within them
    # ------------------------------------------------------------------
    catalog = load_split_tree_catalog()
    if not catalog:
        raise AgenticToolError("No split trees available")

    # 2a: LLM router — pick 1-2 relevant split trees
    selected_tree_ids = route_trees(retrieval_query, catalog, model)
    search_catalog = {tid: catalog[tid] for tid in selected_tree_ids if tid in catalog}
    if not search_catalog:
        search_catalog = catalog  # fallback: search all trees
    print(f"[retriever] step2 trees selected: {list(search_catalog.keys())}")

    # 2b: Hybrid search — keyword candidates + LLM node selection (PageIndex pattern)
    all_node_ids: list[str] = []
    for tid, entry in search_catalog.items():
        ids = _hybrid_search(retrieval_query, entry["structure"], model)
        all_node_ids.extend(ids)
    print(f"[retriever] step2 node_ids found: {all_node_ids[:8]}")

    # 2c: Fetch text for selected node_ids
    all_texts: list[str] = []
    all_sources: list[dict] = []
    seen_ids: set[str] = set()
    for tid, entry in search_catalog.items():
        target_ids = [nid for nid in all_node_ids if nid not in seen_ids]
        if not target_ids:
            continue
        ev_text, ev_sources = _fetch_evidence(entry["structure"], target_ids)
        if ev_text.strip():
            all_texts.append(ev_text)
            for s in ev_sources:
                s["tree_id"] = tid
            all_sources.extend(ev_sources)
            for s in ev_sources:
                node_id = s.get("node_id", "")
                if node_id:
                    seen_ids.add(node_id)

    combined_evidence = "\n\n---\n\n".join(all_texts)[:24000]

    if not combined_evidence.strip():
        # Fallback: pure keyword scoring across all trees
        print("[retriever] step2 hybrid found nothing, falling back to keyword scan")
        combined_evidence, all_sources, _, _ = _gather_tree_evidence(catalog, retrieval_query, **CHAT_RETRIEVAL_CONFIG)

    print(f"[retriever] step2 evidence chars={len(combined_evidence)}, sources={len(all_sources)}")

    # ------------------------------------------------------------------
    # Step 3 — Generate a direct answer from the evidence (single LLM call)
    # ------------------------------------------------------------------
    print("[retriever] step3: generating answer from evidence")
    answer = _generate_answer(answer_query, combined_evidence, model)

    import unicodedata
    answer = unicodedata.normalize("NFKC", answer)
    answer = answer.replace("\u2013", "-").replace("\u2014", "-")
    answer = re.sub(r"<br\s*/?>", "\n", answer, flags=re.IGNORECASE)

    # Deduplicate sources
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for s in all_sources:
        key = (s.get("title", ""), s.get("page_range", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    elapsed_ms = int((time.time() - start_time) * 1000)
    print(f"[retriever] done in {elapsed_ms}ms")

    return AgenticResult(
        answer=answer,
        sources=deduped[:5],
        diagnostics={
            "scanner": scanner,
            "retrieval_query": retrieval_query,
            "selected_trees": list(search_catalog.keys()),
            "node_ids": all_node_ids[:10],
            "elapsed_ms": elapsed_ms,
        },
    )


def agentic_collect_evidence(query: str, model: str = "MiniMax-M2.7") -> tuple[str, list[dict], dict[str, Any]]:
    """Collect raw evidence for requirements extractor / audit — same tree budget as chat."""
    catalog = load_split_tree_catalog()
    if not catalog:
        return "", [], {}

    combined, all_sources, search_diag, branch_diag = _gather_tree_evidence(
        catalog, query, **CHAT_RETRIEVAL_CONFIG
    )
    return combined, all_sources, {"branches": branch_diag, "search": search_diag}
