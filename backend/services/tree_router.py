"""
Tree Router — uses an LLM to decide which bulletin tree(s) to search for a query.

All available trees:
  arts_sciences  → bulletin_arts_sciences.tree.json   (~6.6 MB, Arts & Sciences programs)
  engineering   → bulletin_engineering.tree.json     (~682 KB, Engineering programs)
  business      → bulletin_business.tree.json        (~268 KB, Olin Business)
  architecture  → bulletin_architecture.tree.json     (~401 KB, Architecture)
  art           → bulletin_art.tree.json             (~444 KB, School of Art)
  cross_school  → bulletin_cross_school.tree.json   (~227 KB, university-wide policies)
  university    → bulletin_university.tree.json       (~188 KB, institutional/about)

Routing is LLM-based. Keyword scoring exists only as a fallback when the LLM API
is unavailable or USE_LLM_ROUTING is explicitly disabled.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────

# DATA_DIR must resolve to the same location as main.py's DATA_DIR.
# Since main.py is at backend/main.py, we resolve relative to main.py's parent.
_BACKEND_ROOT = Path(__file__).parent.parent  # = backend/
DATA_DIR = Path(os.getenv("DATA_DIR", str(_BACKEND_ROOT.parent / "data")))  # = gradYOU8/data/

# Setting to "false" disables LLM routing entirely (keyword-only, for dev/debugging)
USE_LLM_ROUTING = os.getenv("USE_LLM_ROUTING", "true").lower() != "false"

# Timeout for the routing LLM call (seconds)
LLM_ROUTE_TIMEOUT = float(os.getenv("LLM_ROUTE_TIMEOUT", "15"))

# ── Tree registry ─────────────────────────────────────────────────────────────

TREE_META: dict[str, dict] = {
    "arts_sciences": {
        "file": "bulletin_arts_sciences.tree.json",
        "school": "Arts & Sciences",
        "description": (
            "Arts & Sciences programs: biology, chemistry, physics, mathematics, "
            "psychology, economics, English, history, philosophy, neuroscience, "
            "biochemistry, data science, and other liberal arts and sciences programs."
        ),
    },
    "engineering": {
        "file": "bulletin_engineering.tree.json",
        "school": "Engineering",
        "description": (
            "School of Engineering programs: Computer Science & Engineering (CSE), "
            "Electrical Engineering (EE), Mechanical Engineering (ME), "
            "Computer Engineering (CE), Chemical Engineering (ChE), "
            "Biomedical Engineering (BME), and other engineering programs."
        ),
    },
    "business": {
        "file": "bulletin_business.tree.json",
        "school": "Business",
        "description": (
            "Olin Business School programs: finance, accounting, marketing, "
            "management, entrepreneurship, business analytics, and supply chain."
        ),
    },
    "architecture": {
        "file": "bulletin_architecture.tree.json",
        "school": "Architecture",
        "description": (
            "School of Architecture programs: architecture, urban planning, "
            "landscape architecture, and built environment studies."
        ),
    },
    "art": {
        "file": "bulletin_art.tree.json",
        "school": "Art",
        "description": (
            "School of Art programs: visual arts, fine arts, painting, sculpture, "
            "photography, film, graphic design, illustration, and art history."
        ),
    },
    "cross_school": {
        "file": "bulletin_cross_school.tree.json",
        "school": "Cross-School",
        "description": (
            "University-wide policies and programs: undergraduate admissions, "
            "financial support and scholarships, tuition and fees, "
            "majors and minors available across all schools, "
            "Beyond Boundaries interdisciplinary program, "
            "and other cross-school academic opportunities."
        ),
    },
    "university": {
        "file": "bulletin_university.tree.json",
        "school": "University",
        "description": (
            "University institutional information: about Washington University, "
            "preface, university policies, VA appendix, and the index."
        ),
    },
}

# ── Routing prompt ────────────────────────────────────────────────────────────

TREE_LIST_BLOCK = "\n".join(
    f"  - {tid}: {meta['description']}"
    for tid, meta in TREE_META.items()
)

LLM_ROUTE_PROMPT = """A student is asking about WashU degree requirements. Which tree(s) should we search?

Query: {query}

Available trees:
{TREE_LIST_BLOCK}

Return ONLY valid JSON:
{{"trees": ["tree_id1", ...], "reason": "one sentence explanation"}}

Rules:
- If the query is about a specific school's programs or courses → include that school's tree
- If the query is about university-wide information (admissions, tuition, gen ed, all-school listings) → include "cross_school"
- If the query is about institutional/about WashU content → include "university"
- If the query is ambiguous or mentions multiple schools → include all relevant school trees
- Never return more than 3 trees unless it's clearly a cross-school or university-wide query
""".strip()

# ── Keyword fallback (emergency only) ─────────────────────────────────────────
# Used ONLY when LLM routing is disabled or the API call fails.
# These are intentionally minimal — they just prevent total failure, not guide routing.

# Keyword scoring for emergency fallback (when LLM is unavailable).
# Higher specificity = higher score so the most specific match wins.
# Each keyword hit earns +1.0 point. The high-confidence threshold is 4.0.
_KEYWORD_MAP: dict[str, list[str]] = {
    # Arts & Sciences — specific programs (high specificity)
    "arts_sciences": [
        "arts and sciences", "arts & sciences",
        # Specific majors
        "biology major", "biology minor", "bio major", "computational biology",
        "chemistry major", "physics major", "math major", "mathematics major",
        "psychology major", "economics major", "neuroscience major", "biochemistry major",
        "data science major", "data science minor",
        # General discipline keywords (lower specificity, only fires if query is short)
        "biology", "bio", "chemistry", "physics", "math", "psychology", "economics",
        "neuroscience", "biochemistry", "pre-med", "premed", "pre-medicine",
    ],
    "engineering": [
        "engineering", "school of engineering",
        "cse", "computer science and engineering",
        "electrical engineering", "mechanical engineering", "computer engineering",
        "chemical engineering", "biomedical engineering", "systems engineering",
    ],
    "business": [
        "business", "olin business", "finance major", "accounting major",
        "marketing major", "management major", "entrepreneurship",
        "business analytics",
    ],
    "architecture": [
        "architecture", "architectural", "urban planning", "landscape architecture",
    ],
    "art": [
        "art", "visual arts", "fine arts", "painting", "sculpture",
        "photography", "film", "graphic design", "art history",
    ],
    # Cross-school — policies and general academic terms (low specificity, lower priority)
    "cross_school": [
        "admission", "admissions", "apply", "applicant",
        "tuition", "fees", "financial support", "financial aid", "scholarship",
        "general education", "gen ed", "breadth requirement",
        "cross-school", "cross school",
    ],
    "university": [
        "washington university", "washu", "about", "preface", "campuses",
    ],
}


def _keyword_fallback(query: str) -> list[str]:
    """Emergency fallback when LLM routing is unavailable. Returns list of tree IDs."""
    q = query.lower()
    scores: dict[str, float] = {tid: 0.0 for tid in TREE_META}

    for tid, kws in _KEYWORD_MAP.items():
        for kw in kws:
            if kw.lower() in q:
                scores[tid] += 1.0

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    selected = [tid for tid, score in ranked if score > 0]
    return selected if selected else ["arts_sciences"]


# ── Tree cache ────────────────────────────────────────────────────────────────

_tree_cache: dict[str, dict] = {}


def get_tree(tree_id: str) -> dict:
    """Load (or return cached) tree by ID. Raises FileNotFoundError if not found."""
    if tree_id in _tree_cache:
        return _tree_cache[tree_id]

    meta = TREE_META.get(tree_id)
    if not meta:
        raise ValueError(f"Unknown tree_id: {tree_id}")

    path = DATA_DIR / meta["file"]
    if not path.exists():
        raise FileNotFoundError(f"Tree not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Tree files are lists of root nodes. Wrap them so tree_retrieve can call
    # tree.get("structure", []) — it expects {structure: [root_nodes]}.
    if isinstance(raw, list):
        tree = {"structure": raw}
    else:
        tree = raw

    _tree_cache[tree_id] = tree
    return tree


def get_all_tree_ids() -> list[str]:
    return list(TREE_META.keys())


def get_tree_info() -> dict:
    """Return metadata about available trees (does not load tree content)."""
    return {
        tid: {
            "school": meta["school"],
            "file": meta["file"],
            "description": meta["description"],
            "loaded": tid in _tree_cache,
        }
        for tid, meta in TREE_META.items()
    }


# ── LLM routing ───────────────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    """Try to get MiniMax API key from env or openclaw config."""
    token = os.getenv("MINIMAX_API_KEY", "")
    if token:
        return token

    try:
        auth_path = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
        with open(auth_path) as f:
            profiles = json.load(f)
        for name, cfg in profiles.get("profiles", {}).items():
            if "minimax" in name.lower():
                return cfg.get("access")
    except Exception:
        pass

    return None


def llm_route(query: str) -> list[str]:
    """
    Use MiniMax to decide which tree(s) to search.

    Returns a list of tree IDs. On any failure, falls back to keyword scoring.
    """
    if not USE_LLM_ROUTING:
        return _keyword_fallback(query)

    token = _get_api_key()
    if not token:
        return _keyword_fallback(query)

    prompt = LLM_ROUTE_PROMPT.format(
        query=query,
        TREE_LIST_BLOCK=TREE_LIST_BLOCK,
    )

    payload = json.dumps({
        "model": "MiniMax-M2.7",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
    }).encode()

    import urllib.request

    req = urllib.request.Request(
        "https://api.minimax.io/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=LLM_ROUTE_TIMEOUT) as r:
            result = json.loads(r.read())
            raw = result["choices"][0]["message"]["content"]
    except Exception:
        return _keyword_fallback(query)

    try:
        parsed = json.loads(raw) if raw.startswith("{") else {}
        trees = parsed.get("trees", [])
        valid = [t for t in trees if t in TREE_META]
        if valid:
            return valid
    except Exception:
        pass

    # MiniMax may wrap the JSON in <thinking> blocks or prefix with commentary.
    # Try to extract JSON from anywhere in the raw response.
    import re
    json_match = re.search(r'\{[^{}]*"trees"[^}]*\}', raw, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            trees = parsed.get("trees", [])
            valid = [t for t in trees if t in TREE_META]
            if valid:
                return valid
        except Exception:
            pass

    return _keyword_fallback(query)


# ── Public API ───────────────────────────────────────────────────────────────

def route(query: str) -> list[str]:
    """
    Decide which tree(s) to search for a given query.

    Uses LLM routing. Falls back to keyword scoring only when the LLM is
    unavailable or USE_LLM_ROUTING=false.

    Returns:
        Ordered list of tree IDs to search, most relevant first.
    """
    return llm_route(query)


def route_and_retrieve(query: str, model: str = "MiniMax-M2.7") -> tuple[str, list[dict]]:
    """
    Route the query to the right tree(s), retrieve from each, and synthesize.

    Args:
        query: the student's question
        model: LLM model to use for tree_retrieve and synthesis

    Returns:
        (answer, sources) — answer is a string, sources is a list of dicts
        with keys: title, page_range, text, tree, school

    Raises:
        RuntimeError if no trees can be loaded.
    """
    from main import tree_retrieve  # lazy import to avoid circular dependency

    tree_ids = route(query)

    all_answers: list[str] = []
    all_sources: list[dict] = []

    for tid in tree_ids:
        try:
            tree = get_tree(tid)
        except Exception:
            continue

        school = TREE_META[tid]["school"]
        answer, sources = tree_retrieve(query, tree, model=model)

        # Tag each source with its tree so the frontend knows where it came from
        for s in sources:
            s["tree"] = tid
            s["school"] = school

        all_answers.append(f"[{school} Bulletin]\n{answer}")
        all_sources.extend(sources)

        # Stop early if we got a good answer and remaining trees are unlikely to add value
        if len(answer) > 80 and "couldn't find" not in answer.lower():
            remaining = tree_ids[tree_ids.index(tid) + 1:]
            any_relevant = any(
                TREE_META[t].get("description", "") and
                any(kw in query.lower() for kw in TREE_META[t]["description"].lower().split())
                for t in remaining
            )
            if not any_relevant:
                break

    # Deduplicate sources by title
    seen_titles: set[str] = set()
    deduped: list[dict] = []
    for s in all_sources:
        if s["title"] not in seen_titles:
            seen_titles.add(s["title"])
            deduped.append(s)

    # Synthesize if multiple trees were consulted
    if len(all_answers) > 1:
        synthesis = _synthesize(query, all_answers)
    else:
        synthesis = all_answers[0] if all_answers else "I couldn't find relevant information."

    return synthesis, deduped


def _synthesize(query: str, answers: list[str]) -> str:
    """
    Use MiniMax to synthesize multiple tree answers into a single coherent response.
    Called only when more than one tree was consulted.
    """
    token = _get_api_key()
    if not token:
        return answers[0] if answers else ""

    answers_block = "\n\n---\n\n".join(answers)

    prompt = (
        f"A student asks: {query}\n\n"
        f"You consulted multiple WashU bulletins and got the following answers:\n\n"
        f"{answers_block}\n\n"
        f"Synthesize these into a single clear, accurate answer. "
        f"If the answers disagree, note the discrepancy. "
        f"Cite specific course numbers and unit counts where possible."
    )

    payload = json.dumps({
        "model": "MiniMax-M2.7",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8000,
    }).encode()

    import urllib.request

    req = urllib.request.Request(
        "https://api.minimax.io/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
            raw = result["choices"][0]["message"]["content"]
            raw = raw.replace("<think>", "").replace("</think>", "")
            return raw.strip()
    except Exception:
        return answers[0] if answers else ""
