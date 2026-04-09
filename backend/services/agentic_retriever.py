"""
PageIndex single-shot tree search + MiniMax retriever.

3-call pipeline matching PageIndex's canonical pattern:
  1. Combined LLM call: route to relevant split tree(s) + identify program focus
  2. Parallel single-shot LLM tree search: each selected tree gets one LLM call
     that sees the full hierarchical outline and picks node IDs directly
  3. MiniMax generates the final answer from fetched node text

Reduces from 4-5 serial LLM calls to 2-3 with per-tree parallelism.
"""
from __future__ import annotations

import asyncio
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
# Step 1: Combined router + program focus (single LLM call)
# ---------------------------------------------------------------------------

def _build_router_focus_prompt(query: str, catalog: dict[str, dict[str, Any]]) -> str:
    lines = []
    for tree_id, entry in catalog.items():
        lines.append(f"- {tree_id}: {entry.get('summary', '')[:200]}")
    ctx = "\n".join(lines)
    return (
        "You are routing a WashU bulletin query to the correct document trees and identifying "
        "the program being asked about.\n\n"
        f"Available trees:\n{ctx}\n\n"
        f"Student question: \"{query}\"\n\n"
        "Return ONLY a single JSON object:\n"
        '{"selected_tree_ids": ["<tree_id>"], "program_name": "", "program_type": "", "retrieval_query": ""}\n\n'
        "Rules:\n"
        "- selected_tree_ids: 1-2 IDs from the available list above only.\n"
        "- program_name: exact WashU program name, or empty string if none.\n"
        "- program_type: \"major\", \"minor\", or empty string. Only set to \"major\" when "
        "identifying a degree program (e.g. 'biology major'), NOT when 'major' is an adjective "
        "(e.g. 'major requirements').\n"
        "- retrieval_query: if program_name and program_type are set, use "
        "\"what are the requirements for the <program_name> <program_type>\". "
        "Otherwise lightly restate the question as a short requirement-focused query.\n"
        "Return valid JSON only, no explanation."
    )


def _route_and_focus(
    query: str,
    catalog: dict[str, dict[str, Any]],
    model: str,
) -> dict[str, Any]:
    """Single LLM call that routes to relevant trees AND identifies program focus.

    Returns dict with keys: selected_tree_ids, program_name, program_type, retrieval_query.
    Falls back to keyword heuristics if the LLM fails or returns invalid tree IDs.
    """
    from pageindex_agent.utils import ChatGPT_API

    def _keyword_fallback() -> dict[str, Any]:
        ql = query.lower()
        is_policy = any(k in ql for k in ["policy", "pass/fail", "grade", "deadline", "residency", "credit"])
        is_program = any(k in ql for k in ["major", "minor", "requirement", "program", "degree"])
        if is_policy:
            order = ["university", "cross_school", "arts_sciences", "engineering", "business", "architecture", "art"]
        elif is_program:
            order = ["arts_sciences", "engineering", "cross_school", "business", "architecture", "art", "university"]
        else:
            order = ["arts_sciences", "engineering", "university", "cross_school", "business", "architecture", "art"]
        return {
            "selected_tree_ids": [tid for tid in order if tid in catalog][:3],
            "program_name": "",
            "program_type": "",
            "retrieval_query": query,
        }

    prompt = _build_router_focus_prompt(query, catalog)
    try:
        raw = ChatGPT_API(model, prompt, stream=False) or ""
        raw = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"<thinking[\s\S]*?</thinking>", "", raw, flags=re.IGNORECASE)
        parsed = _extract_first_json_object(raw)
    except AgenticParseError:
        print("[retriever] router parse fail, using keyword fallback")
        return _keyword_fallback()
    except Exception as e:
        print(f"[retriever] router call failed: {e}, using keyword fallback")
        return _keyword_fallback()

    raw_ids = parsed.get("selected_tree_ids", [])
    selected = [x for x in raw_ids if isinstance(x, str) and x in catalog]
    if not selected:
        print(f"[retriever] router returned invalid ids: {raw_ids!r}, using keyword fallback")
        return _keyword_fallback()

    program_name = str(parsed.get("program_name", "") or "").strip()
    program_type = str(parsed.get("program_type", "") or "").strip().lower()
    if program_type not in {"major", "minor"}:
        program_type = ""

    # Build a clean retrieval query
    if program_name and program_type:
        name_tail = program_name.lower().rstrip(". ")
        if name_tail.endswith(program_type) or name_tail.endswith(", b.a") or name_tail.endswith(", b.s"):
            retrieval_query = f"what are the requirements for the {program_name}"
        else:
            retrieval_query = f"what are the requirements for the {program_name} {program_type}"
    else:
        retrieval_query = str(parsed.get("retrieval_query", "") or "").strip() or query

    result = {
        "selected_tree_ids": selected[:2],
        "program_name": program_name,
        "program_type": program_type,
        "retrieval_query": retrieval_query,
    }
    print(f"[retriever] router: trees={selected[:2]} program={program_name!r} type={program_type!r}")
    return result


# ---------------------------------------------------------------------------
# Step 2: Single-shot LLM tree search (PageIndex canonical pattern)
# ---------------------------------------------------------------------------

def _prepare_tree_for_search(structure: list[dict], max_depth: int = 4) -> str:
    """Format tree as a compact hierarchical outline with node_ids for the LLM.

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
    # Earth science → full WashU department name for keyword matching
    (r"\bearth\s+sci\w*", "earth environmental and planetary sciences"),
    (r"\beeps\b", "earth environmental and planetary sciences"),
]


def _expand_query(query: str) -> str:
    """Expand abbreviations in query for better keyword matching."""
    q = query.lower()
    for pattern, replacement in _QUERY_EXPANSIONS:
        q = re.sub(pattern, replacement, q)
    return q


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
    Two-step hierarchical retrieval used as the keyword fallback path:
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
                score = _score_node(root, terms, type_words)
                if score >= 3:
                    branch_candidates.append((score, tree_id, root, root.get("title", "")))
                continue
            for child in first_level:
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
    """Fast keyword search over node titles, summaries, and text to find candidates."""
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


def _single_shot_tree_search(
    tree_id: str,
    entry: dict[str, Any],
    retrieval_query: str,
    model: str,
) -> list[str]:
    """PageIndex canonical pattern: feed the full tree outline to the LLM, get node IDs back.

    The LLM sees the complete hierarchical structure and can navigate parent-child
    relationships — unlike keyword pre-filtering which misses nodes with non-obvious titles.
    Falls back to keyword scoring if the LLM call fails or returns nothing.
    """
    from pageindex_agent.utils import ChatGPT_API

    structure = entry.get("structure") or []
    label = entry.get("label", tree_id)
    tree_outline = _prepare_tree_for_search(structure)

    if not tree_outline.strip():
        return []

    prompt = (
        f"You are selecting the most relevant sections from the WashU Undergraduate Bulletin "
        f"({label}) to answer a student's question.\n\n"
        f"Question: \"{retrieval_query}\"\n\n"
        f"Bulletin section outline:\n{tree_outline}\n\n"
        "Each line: [node_id] Title (pages X-Y, N children) — summary\n\n"
        "Select 2-5 node_ids that most directly contain the answer. "
        "Prefer nodes with specific requirement tables over general descriptions. "
        "If a parent node clearly contains the requirement text, select the parent "
        "rather than every individual child.\n\n"
        "Reply ONLY with a JSON array of node IDs: [\"node_id1\", \"node_id2\"]"
    )

    try:
        raw = ChatGPT_API(model, prompt, stream=False) or ""
        raw = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"<thinking[\s\S]*?</thinking>", "", raw, flags=re.IGNORECASE)
        ids = _extract_json_array(raw)
        valid = [str(nid) for nid in ids if nid and str(nid).strip()]
        if valid:
            print(f"[retriever] single_shot tree={tree_id} selected={valid[:5]}")
            return valid
    except Exception as e:
        print(f"[retriever] single_shot tree={tree_id} failed: {e}, falling back to keywords")

    # Fallback: keyword scoring
    candidates = _keyword_candidates(structure, retrieval_query, max_results=4)
    return [n.get("node_id", "") for n in candidates if n.get("node_id")]


async def _parallel_tree_search(
    search_catalog: dict[str, dict[str, Any]],
    retrieval_query: str,
    model: str,
) -> list[str]:
    """Run _single_shot_tree_search for each selected tree concurrently.

    Uses asyncio.to_thread so the synchronous ChatGPT_API HTTP calls run in
    parallel thread pool workers — wall-clock time becomes max(T_tree1, T_tree2)
    instead of T_tree1 + T_tree2.
    """
    tasks = [
        asyncio.to_thread(_single_shot_tree_search, tid, entry, retrieval_query, model)
        for tid, entry in search_catalog.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_ids: list[str] = []
    for tid, result in zip(search_catalog.keys(), results):
        if isinstance(result, Exception):
            print(f"[retriever] parallel search failed for {tid}: {result}")
            continue
        all_ids.extend(result)
    return all_ids


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


_REQUIREMENTS_HEADERS = [
    "major requirements",
    "program requirements",
    "degree requirements",
    "requirements for the major",
    "requirements for the minor",
    "minor requirements",
    "course requirements",
    "total units required",
]


def _extract_relevant_slice(text: str, cap: int) -> str:
    """Return the most relevant slice of a long node's text.

    For nodes where requirement details are buried after thousands of characters
    of course listings, find the earliest section header that signals structured
    requirement content and start the excerpt from there instead of position 0.
    """
    if len(text) <= cap:
        return text

    text_l = text.lower()
    best_pos = len(text)
    for header in _REQUIREMENTS_HEADERS:
        idx = text_l.find(header)
        if 0 < idx < best_pos:
            best_pos = idx

    if best_pos < len(text) - 100:
        start = max(0, best_pos - 100)
        return text[start : start + cap]

    return text[:cap]


def _fetch_evidence(structure: list[dict], node_ids: list[str]) -> tuple[str, list[dict]]:
    """Fetch text for the given node_ids and return (combined_text, sources)."""
    target_set = set(node_ids)
    nodes = _find_nodes_by_ids(structure, target_set)

    texts: list[str] = []
    sources: list[dict] = []
    char_budget = 32000
    per_node_cap = 20000

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
        cap = min(remain, per_node_cap)
        node_text = _extract_relevant_slice(text, cap)
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
    """Generate a final answer from the fetched evidence."""
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
        f"Bulletin content:\n{evidence_text[:24000]}\n\n"
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
    """Keyword-only hierarchical node pick. Used as fallback when LLM search returns nothing."""
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
    3-call retrieval pipeline matching PageIndex's canonical pattern:

      Step 1 (LLM): Combined router + program focus — picks relevant trees and
                    derives a precise retrieval query in a single call.
      Step 2 (LLM, parallel): Single-shot tree search — each selected tree gets
                    one LLM call that sees the full hierarchical outline and picks
                    node IDs directly. Per-tree calls run in parallel via asyncio.
      Step 3 (LLM): Generate the final answer from fetched node text.
    """
    start_time = time.time()

    catalog = load_split_tree_catalog()
    if not catalog:
        raise AgenticToolError("No split trees available")

    # Augment answer query with student context when available
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
    # Step 1 — Combined router + focus (1 LLM call)
    # ------------------------------------------------------------------
    print("[retriever] step1: routing + identifying program focus")
    router = _route_and_focus(query, catalog, model)
    selected_tree_ids = router["selected_tree_ids"]
    retrieval_query = router["retrieval_query"]
    print(f"[retriever] step1 done: trees={selected_tree_ids} query={retrieval_query!r}")

    search_catalog = {tid: catalog[tid] for tid in selected_tree_ids if tid in catalog}
    if not search_catalog:
        search_catalog = catalog

    # ------------------------------------------------------------------
    # Step 2 — Parallel single-shot tree search (PageIndex pattern)
    # ------------------------------------------------------------------
    print(f"[retriever] step2: single-shot search across {list(search_catalog.keys())}")
    # asyncio.run is safe here: agentic_retrieve runs in a thread pool worker
    # (dispatched via loop.run_in_executor from the FastAPI handler), so there
    # is no running event loop in this thread.
    all_node_ids = asyncio.run(_parallel_tree_search(search_catalog, retrieval_query, model))
    print(f"[retriever] step2 node_ids: {all_node_ids[:8]}")

    # Fetch text for selected node_ids
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
            seen_ids.update(s.get("title", "") for s in ev_sources)

    combined_evidence = "\n\n---\n\n".join(all_texts)[:24000]

    if not combined_evidence.strip():
        # Fallback: pure keyword scoring across all trees
        print("[retriever] step2 found nothing, falling back to keyword scan")
        combined_evidence, all_sources, _, _ = _gather_tree_evidence(catalog, retrieval_query, **CHAT_RETRIEVAL_CONFIG)

    print(f"[retriever] step2 evidence chars={len(combined_evidence)}, sources={len(all_sources)}")

    # ------------------------------------------------------------------
    # Step 3 — Generate answer (1 LLM call)
    # ------------------------------------------------------------------
    print("[retriever] step3: generating answer")
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
            "router": router,
            "retrieval_query": retrieval_query,
            "selected_trees": list(search_catalog.keys()),
            "node_ids": all_node_ids[:10],
            "elapsed_ms": elapsed_ms,
        },
    )


def agentic_collect_evidence(query: str, model: str = "MiniMax-M2.7") -> tuple[str, list[dict], dict[str, Any]]:
    """Collect raw evidence for requirements extractor / audit.

    Uses pure keyword scoring across all trees — no LLM needed since audit
    queries are always specific program names that match node titles directly.
    Uses _fetch_evidence (with _extract_relevant_slice) so requirements buried
    deep in long nodes are captured correctly.
    """
    catalog = load_split_tree_catalog()
    if not catalog:
        return "", [], {}

    # Keyword scan across all trees — score every node, keep top 8
    scored: list[tuple[int, str, str]] = []  # (score, tree_id, node_id)
    for tid, entry in catalog.items():
        candidates = _keyword_candidates(entry["structure"], query, max_results=8)
        for node in candidates:
            nid = node.get("node_id", "")
            if nid:
                scored.append((node.get("_kw_score", 0), tid, nid))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:8]

    # Group node IDs by tree, fetch text using _extract_relevant_slice
    by_tree: dict[str, list[str]] = {}
    for _, tid, nid in top:
        by_tree.setdefault(tid, []).append(nid)

    all_texts: list[str] = []
    all_sources: list[dict] = []
    for tid, node_ids in by_tree.items():
        ev_text, ev_sources = _fetch_evidence(catalog[tid]["structure"], node_ids)
        if ev_text.strip():
            all_texts.append(ev_text)
            all_sources.extend(ev_sources)

    combined = "\n\n---\n\n".join(all_texts)
    return combined, all_sources, {}
