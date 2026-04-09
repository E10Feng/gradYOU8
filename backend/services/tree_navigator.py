"""
LLM-Driven Hierarchical Tree Navigator for WashU Bulletin.

Replaces flat-list LLM routing with guided tree traversal.
The LLM explores multiple branches in parallel, remembers all paths checked,
and only fetches pages from nodes that look relevant.

Internal reasoning only — the user never sees navigation steps.
"""
from __future__ import annotations

import json, re, sys
from dataclasses import dataclass, field
from pathlib import Path

_BACKEND_ROOT = Path(__file__).parent.parent
DATA_DIR = _BACKEND_ROOT.parent / "data"

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class NodeRef:
    """A node in the navigation frontier."""
    title: str
    summary: str
    start_index: int
    end_index: int
    children_count: int
    depth: int
    path: list[str] = field(default_factory=list)
    text_preview: str = ""
    raw_text: str = ""


@dataclass
class ExploreDecision:
    """LLM's decision for the current frontier."""
    to_fetch: list[int]      # indices of sections to get PDF pages from
    to_expand: list[int]     # indices of sections to explore children of
    reasoning: str           # INTERNAL USE ONLY — never exposed to user


@dataclass
class NavigationResult:
    """Outcome of tree navigation."""
    nodes_to_fetch: list[NodeRef] = field(default_factory=list)
    explored_paths: list[NodeRef] = field(default_factory=list)
    did_find: bool = False


# ── Tree helpers ──────────────────────────────────────────────────────────────

def _clean_title(title: str) -> str:
    """Remove HTML entities and normalize."""
    return title.replace("&#39;", "'").replace("&amp;", "&")


def _build_node_ref(node: dict, depth: int, path: list[str]) -> NodeRef:
    """Convert a tree node dict to a NodeRef."""
    return NodeRef(
        title=_clean_title(node.get("title", "")),
        summary=(node.get("summary") or "")[:200].replace("\n", " ").strip(),
        start_index=node.get("start_index", 0),
        end_index=node.get("end_index", node.get("start_index", 0)),
        children_count=len(node.get("nodes") or []),
        depth=depth,
        path=path[:],
        text_preview=(node.get("text") or "")[:200].replace("\n", " ").strip(),
        raw_text=(node.get("text") or ""),
    )


def _get_children(node_ref: NodeRef, tree: list[dict]) -> list[NodeRef]:
    """Find the children of the given node in the tree."""
    def walk(nodes, depth, path):
        results = []
        for node in nodes:
            title = _clean_title(node.get("title", ""))
            start = node.get("start_index", 0)
            if title == node_ref.title and start == node_ref.start_index:
                children = node.get("nodes") or []
                for child in children:
                    results.append(_build_node_ref(child, depth + 1, path + [title]))
                return results
            if node.get("nodes"):
                results.extend(walk(node["nodes"], depth, path))
        return results

    return walk(tree, node_ref.depth, node_ref.path[:-1]) if node_ref.path else walk(tree, 0, [])


def _load_tree_raw() -> list[dict]:
    """Load the raw bulletin tree for debug/local inspection only.

    Query-time retrieval should pass explicit `tree` data into `navigate_tree`
    and should not rely on this helper.
    """
    split_names = [
        "bulletin_architecture.tree.json",
        "bulletin_arts_sciences.tree.json",
        "bulletin_engineering.tree.json",
        "bulletin_art.tree.json",
        "bulletin_university.tree.json",
        "bulletin_cross_school.tree.json",
        "bulletin_business.tree.json",
    ]
    split_paths = [DATA_DIR / n for n in split_names if (DATA_DIR / n).exists()]
    if split_paths:
        merged: list[dict] = []
        for p in split_paths:
            with open(p, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                merged.extend(raw)
            elif isinstance(raw, dict):
                merged.extend(raw.get("structure", []))
        return merged

    tree_path = DATA_DIR / "bulletin_full.tree.json"
    if not tree_path.exists():
        return []
    with open(tree_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw if isinstance(raw, list) else raw.get("structure", [])


# ── LLM decision ──────────────────────────────────────────────────────────────

def _format_frontier(frontier: list[NodeRef]) -> str:
    """Format the frontier as a readable block for the LLM."""
    lines = []
    for i, node in enumerate(frontier):
        path_str = " > ".join(node.path + [node.title]) if node.path else node.title
        lines.append(
            f"Frontier item {i}:\n"
            f"  Title: [{node.start_index}-{node.end_index}] {node.title}\n"
            f"  Summary: {node.summary}\n"
            f"  Children: {node.children_count}\n"
            f"  Path: {path_str}"
        )
    return "\n\n".join(lines)


def _canonical_tokens(canonical_hint: str | None) -> list[str]:
    """Extract useful canonical target tokens (e.g., computer/science/minor)."""
    if not canonical_hint:
        return []
    stop = {"major", "minor", "specialization", "concentration", "requirements", "and"}
    tokens = re.findall(r"[a-z0-9]+", canonical_hint.lower())
    return [t for t in tokens if t not in stop and len(t) >= 3]


def _node_match_score(node: NodeRef, canonical_hint: str | None) -> int:
    """Score node relevance against canonical target using title/path overlap."""
    if not canonical_hint:
        return 0
    target = (canonical_hint + " " + " ".join(_canonical_tokens(canonical_hint))).lower()
    hay = (" ".join(node.path + [node.title])).lower()
    score = 0
    for tok in _canonical_tokens(canonical_hint):
        if tok in hay:
            score += 2
    if canonical_hint.lower() in hay:
        score += 4
    # Small boost for exact type words present in title/path
    if "minor" in canonical_hint.lower() and "minor" in hay:
        score += 2
    if "major" in canonical_hint.lower() and "major" in hay:
        score += 2
    return score


def _query_requests_requirements(query: str) -> bool:
    q = (query or "").lower()
    return any(k in q for k in ["requirement", "requirements", "required courses", "major requirements", "minor requirements"])


def _node_has_requirement_signal(node: NodeRef) -> bool:
    text = ((node.title or "") + "\n" + (node.raw_text or "")).lower()
    markers = [
        "program requirements",
        "required courses",
        "total units required",
        "|  code | title | units",
        "core courses",
        "core requirements",
        "electives",
        "units required",
        "choose one of the following",
    ]
    return any(m in text for m in markers)


def _llm_decide(
    query: str,
    frontier: list[NodeRef],
    model: str = "MiniMax-M2.7",
    canonical_hint: str | None = None,
    keyword_hints: list[dict] | None = None,
) -> ExploreDecision:
    """
    Ask the LLM to decide which frontier nodes to fetch and which to expand.
    Internal reasoning only — not returned to the user.
    Uses non-streaming API for speed and compatibility with threaded contexts.
    """
    import re
    sys.path.insert(0, str(_BACKEND_ROOT / "libs" / "pageindex_agent"))
    try:
        from pageindex_agent.utils import ChatGPT_API
    except Exception:
        return ExploreDecision(to_fetch=[], to_expand=[], reasoning="import_error")

    sections_block = _format_frontier(frontier)
    hint_parts = []
    if canonical_hint:
        hint_parts.append("The student is looking for '" + canonical_hint + "'.")
    if keyword_hints:
        top = ", ".join(
            h["title"] + " (pages " + str(h["start_index"]) + "-" + str(h["end_index"]) + ")"
            for h in keyword_hints[:3]
        )
        hint_parts.append("Keyword analysis found: " + top + ". You may FETCH these directly if they appear in your frontier.")
    hint_block = ("\n\nHints: " + " ".join(hint_parts)) if hint_parts else ""

    prompt = (
        'You are navigating the WashU Undergraduate Bulletin tree to answer a student question.\n\n'
        'Student question: "' + query + '"' + hint_block + '\n\n'
        'Here is your current frontier of document sections. For each, you see its title, summary, page range, and how many child sections it has.\n\n'
        + sections_block + '\n\n'
        'Your task: decide which sections to FETCH (get their PDF pages) and which to EXPAND (look at their children).\n\n'
        'Rules:\n'
        "- IMPORTANT: If a section has Children > 0, you MUST EXPAND it (not FETCH). Child sections contain finer-grained content.\n"
        "- Only FETCH sections that have Children = 0 (leaf nodes) and whose title directly answers the question.\n"
        "- If the canonical program hint appears in a section title/path, prioritize that section.\n"
        "- Avoid unrelated policy/credit/placement sections unless the question explicitly asks about policy.\n"
        "- If a section might contain the answer but you are not sure -> EXPAND it.\n"
        "- If a section is clearly irrelevant (wrong topic) -> skip it.\n"
        '- You may FETCH and EXPAND multiple different sections in one step.\n'
        '- Prefer EXPANDing over FETCHing when in doubt.\n\n'
        'Return ONLY valid JSON with this structure:\n'
        '{"to_fetch": [0, 3], "to_expand": [1, 2], "reasoning": "internal note"}\n\n'
        'If nothing in the frontier seems relevant: {"to_fetch": [], "to_expand": [], "reasoning": "nothing_relevant"}'
    )

    try:
        response = ChatGPT_API(model, prompt, stream=False) or ""
        response = re.sub(r"<thinking[\s\S]*?</thinking>", "", response, flags=re.IGNORECASE)
        json_start = response.find("{")
        json_end = response.rfind("}")
        if json_start == -1 or json_end == -1:
            return ExploreDecision(to_fetch=[], to_expand=[], reasoning="no_json")
        result = json.loads(response[json_start:json_end + 1])
        to_fetch = [int(x) for x in result.get("to_fetch", []) if isinstance(x, (int, str))]
        to_expand = [int(x) for x in result.get("to_expand", []) if isinstance(x, (int, str))]
        return ExploreDecision(
            to_fetch=[i for i in to_fetch if 0 <= i < len(frontier)],
            to_expand=[i for i in to_expand if 0 <= i < len(frontier)],
            reasoning=result.get("reasoning", ""),
        )
    except Exception:
        return ExploreDecision(to_fetch=[], to_expand=[], reasoning="exception")




# ── Direct title search (shortcut for deeply nested nodes) ─────────────────────

_QUERY_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "has",
    "what", "when", "where", "who", "how", "which", "this", "that", "with",
    "from", "about", "into", "have", "does", "requirements", "requirement",
    "required", "courses", "program", "tell", "list", "show", "need",
}


def _extract_query_keywords(query: str) -> tuple[list[str], list[str]]:
    """Extract subject keywords and type words (major/minor/etc.) from a raw query."""
    q = query.lower()
    type_words = []
    for tw in ("minor", "major", "specialization", "concentration"):
        if tw in q:
            type_words.append(tw)

    words = re.findall(r"[a-z]+", q)
    subject = [
        w for w in words
        if w not in _QUERY_STOPWORDS
        and w not in {"major", "minor", "specialization", "concentration"}
        and len(w) >= 3
    ]
    return subject, type_words


def _search_tree_by_title(
    tree: list[dict],
    canonical_hint: str | None,
    query: str,
) -> list[NodeRef]:
    """
    Walk the entire tree and return nodes whose titles closely match the
    canonical hint or query keywords.  Works with or without a canonical hint.
    """
    if canonical_hint:
        hint_lower = canonical_hint.lower()
        tokens = _canonical_tokens(canonical_hint)
        type_words = []
        for tw in ("minor", "major", "specialization"):
            if tw in hint_lower:
                type_words.append(tw)
    else:
        hint_lower = None
        tokens, type_words = _extract_query_keywords(query)

    if not tokens:
        return []

    major_synonyms = ["bachelor of science", "bachelor of arts", "bs in", "ba in", "b.s.", "b.a."]

    matches: list[tuple[int, NodeRef]] = []

    def walk(nodes: list[dict], depth: int, path: list[str]):
        for node in nodes:
            ref = _build_node_ref(node, depth, path)
            title_lower = ref.title.lower()
            blob_lower = (title_lower + "\n" + (ref.raw_text or "").lower())[:12000]

            score = _node_match_score(ref, canonical_hint) if canonical_hint else 0

            # Title-based scoring using tokens
            subject_hit = sum(1 for t in tokens if t in blob_lower)
            type_hit = any(tw in blob_lower for tw in type_words)
            if "major" in type_words:
                type_hit = type_hit or any(syn in blob_lower for syn in major_synonyms)

            if canonical_hint and canonical_hint.lower() in blob_lower:
                score += 8

            if subject_hit >= len(tokens) and type_hit:
                score += 10
            elif subject_hit >= len(tokens) and not type_words:
                score += 6
            elif subject_hit > 0 and type_hit:
                score += subject_hit * 2

            # Penalize combined/joint programs for standalone queries
            if score >= 8 and hint_lower:
                combined_signals = [" and ", " + ", "joint", "combined"]
                if any(sig in title_lower for sig in combined_signals):
                    title_words = set(title_lower.split()) - set(hint_lower.split())
                    extra_programs = title_words & {"economics", "mathematics", "business", "engineering"}
                    if extra_programs:
                        score -= 6

            if score >= 4:
                matches.append((score, ref))

            children = node.get("nodes") or []
            if children:
                walk(children, depth + 1, path + [_clean_title(node.get("title", ""))])

    walk(tree, 0, [])

    matches.sort(key=lambda x: (x[0], x[1].children_count == 0), reverse=True)
    return [ref for _, ref in matches[:8]]


# ── Main navigator ────────────────────────────────────────────────────────────

def navigate_tree(
    query: str,
    tree: list[dict],
    model: str = "MiniMax-M2.7",
    max_steps: int = 5,
    max_parallel: int = 3,
    canonical_hint: str | None = None,
    keyword_hints: list[dict] | None = None,
) -> NavigationResult:
    """
    LLM-driven hierarchical tree navigation.

    Args:
        query: the user's question
        tree: the full bulletin tree (list of root nodes)
        model: LLM to use
        max_steps: max descent steps (prevents runaway)
        max_parallel: max branches to expand per step
        canonical_hint: optional canonical program name from program_indexer
        keyword_hints: optional top keyword search results to guide navigation

    Returns:
        NavigationResult with nodes_to_fetch, explored_paths, did_find
    """
    if not tree:
        return NavigationResult()

    # Strict agentic mode: start from root frontier and let the LLM decide all traversal.
    nodes_to_fetch: list[NodeRef] = []
    root_refs = [_build_node_ref(node, depth=0, path=[]) for node in tree]
    frontier: list[NodeRef] = root_refs

    explored: list[NodeRef] = []
    steps_taken = 0

    while frontier and steps_taken < max_steps:
        steps_taken += 1

        for node in frontier:
            if node not in explored:
                explored.append(node)

        decision = _llm_decide(query, frontier, model, canonical_hint, keyword_hints)

        if not decision.to_fetch and not decision.to_expand:
            # Ask the LLM one more time to explicitly pick an expansion path.
            if steps_taken == 1 and frontier:
                retry_query = (
                    query
                    + "\nIf nothing is directly answer-bearing yet, you MUST choose at least one frontier item to EXPAND."
                )
                decision = _llm_decide(retry_query, frontier, model, canonical_hint, keyword_hints)
                if not decision.to_fetch and not decision.to_expand:
                    break
            else:
                break

        # Nodes with children should always be expanded, never fetched directly.
        # Children contain finer-grained sections; fetching the parent just gives
        # a 3000-char truncation of 20k+ chars, missing the specific content.
        promoted_to_expand = []
        for idx in decision.to_fetch:
            node = frontier[idx]
            if node.children_count > 0:
                promoted_to_expand.append(idx)
            elif node not in nodes_to_fetch:
                nodes_to_fetch.append(node)

        if promoted_to_expand:
            existing = set(decision.to_expand)
            for idx in promoted_to_expand:
                if idx not in existing:
                    decision.to_expand.append(idx)

        # If model fetched nothing useful and didn't expand, force expansion on
        # the best-matching nodes that have children.
        if not decision.to_expand and frontier:
            ranked = sorted(
                range(len(frontier)),
                key=lambda i: (_node_match_score(frontier[i], canonical_hint), frontier[i].children_count),
                reverse=True,
            )
            decision.to_expand = [
                i for i in ranked
                if frontier[i].children_count > 0
            ][:max_parallel]

        new_frontier: list[NodeRef] = []
        for idx in decision.to_expand[:max_parallel]:
            node = frontier[idx]
            children = _get_children(node, tree)
            for child in children:
                if child not in explored and child not in new_frontier:
                    new_frontier.append(child)

        if not new_frontier:
            break

        frontier = new_frontier

    return NavigationResult(
        nodes_to_fetch=nodes_to_fetch,
        explored_paths=explored,
        did_find=bool(nodes_to_fetch),
    )


# ── Page fetching ─────────────────────────────────────────────────────────────

def fetch_pages(node_refs: list[NodeRef]) -> str:
    """Fetch retrieval text for selected nodes (node text first, then PDF fallback)."""
    sys.path.insert(0, str(_BACKEND_ROOT / "libs" / "pageindex_agent"))
    try:
        from pageindex_agent.utils import get_text_of_pages
    except Exception:
        return ""

    pdf_path = DATA_DIR / "bulletin_full.pdf"
    if not pdf_path.exists():
        return ""

    def _priority(ref: NodeRef) -> tuple[int, int]:
        blob = ((ref.title or "") + "\n" + (ref.raw_text or "")).lower()
        has_requirements = int(any(k in blob for k in [
            "program requirements", "required courses", "total units required", "core courses", "elective", "|  code | title | units"
        ]))
        has_program_type = int((" major" in blob) or (" minor" in blob))
        return (has_requirements, has_program_type)

    texts = []
    for ref in sorted(node_refs, key=_priority, reverse=True):
        try:
            # Prefer tree node text selected by agentic navigation.
            if ref.raw_text and ref.raw_text.strip():
                text = ref.raw_text
            else:
                text = get_text_of_pages(str(pdf_path), ref.start_index, ref.end_index + 2, tag=False)
            text = re.sub(r"(?<=[A-Za-z0-9])\s(?=[A-Za-z0-9])", " ", text)
            text = re.sub(r"([A-Z]{2,})(\d)", r"\1 \2", text)
            text = re.sub(r"\s{2,}", " ", text)
            texts.append(f"[Pages {ref.start_index}-{ref.end_index}] {text[:5000]}")
        except Exception:
            pass

    return "\n\n".join(texts)


# ── Answer generation ─────────────────────────────────────────────────────────

def generate_answer(
    query: str,
    pages_text: str,
    model: str = "MiniMax-M2.7",
) -> str:
    """Generate an answer from fetched page content."""
    if not pages_text.strip():
        return "I couldn't find specific information about that in the WashU Undergraduate Bulletin."

    sys.path.insert(0, str(_BACKEND_ROOT / "libs" / "pageindex_agent"))
    try:
        from pageindex_agent.utils import ChatGPT_API
    except Exception:
        return "Error: could not load LLM."

    prompt = (
        f'You are a WashU degree requirement assistant. Answer based ONLY on the provided bulletin content below.\n'
        f'Be specific with course numbers and unit counts. If the answer is not in the content, say you could not find it.\n'
        f'Do not infer that a program does not exist unless the provided content explicitly states that.\n\n'
        f'Student question: "{query}"\n\n'
        f'Bulletin content:\n{pages_text[:18000]}\n\n'
        f'Answer:'
    )

    try:
        response = ChatGPT_API(model, prompt) or ""
        # Strip thinking/reasoning tags from MiniMax/M2.7 responses
        response = re.sub(r"<thinking[\s\S]*?</thinking>", "", response, flags=re.IGNORECASE)
        response = re.sub(r"<think>[\s\S]*?</think>", "", response, flags=re.IGNORECASE)
        # Also strip MiniMax internal [INST] markers
        response = re.sub(r"\[/?INST\]", "", response, flags=re.IGNORECASE)
        return response.strip()
    except Exception:
        return "I had trouble generating an answer. Please try rephrasing your question."
