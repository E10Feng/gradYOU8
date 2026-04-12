"""
Requirements Extractor — uses unified agentic retrieval for bulletin evidence,
then parses that evidence into structured program/college requirement groups.
"""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional

# ── Path setup (same pattern as main.py) ─────────────────────────────────────
_BACKEND_ROOT = Path(__file__).parent.parent
LIBS_PATH = _BACKEND_ROOT / "libs" / "pageindex_agent"
if str(LIBS_PATH) not in sys.path:
    sys.path.insert(0, str(LIBS_PATH))

from services.llm import complete
from services.agentic_retriever import agentic_collect_evidence
from services.program_indexer import extract_programs_from_query


def _normalize_evidence(text: str) -> str:
    """Normalize Unicode in bulletin evidence to safe ASCII-compatible form.

    The bulletin PDF contains Unicode dashes (\\u2011 non-breaking hyphen, en/em
    dashes, etc.) that cause UnicodeEncodeError on Windows cp1252 terminals when
    the LLM API wrapper prints the request or response internally.
    """
    text = unicodedata.normalize("NFKC", text)
    for ch in "\u2011\u2012\u2013\u2014\u2015":  # various dash variants
        text = text.replace(ch, "-")
    return text

# ── Model ─────────────────────────────────────────────────────────────────────
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")

# ── Data paths ───────────────────────────────────────────────────────────────
DATA_DIR = _BACKEND_ROOT.parent / "data"


def _get_bulletin_pdf() -> Path:
    default = DATA_DIR / "bulletin_full.pdf"
    return Path(os.getenv("BULLETIN_PDF", str(default)))


def _load_tree() -> dict:
    """Deprecated in agentic mode; retained for compatibility."""
    return {"structure": []}


# Legacy keyword_tree_search removed — all retrieval uses agentic_collect_evidence.


# ── In-memory cache ──────────────────────────────────────────────────────────
_cache: dict[str, dict] = {}


# ── Parsing prompt ─────────────────────────────────────────────────────────────
EXTRACT_PROMPT = """You are a WashU degree requirements parser. Given raw bulletin text,
extract structured requirement groups for EXACTLY this program: {program_name}

IMPORTANT: Only extract requirements for "{program_name}" — ignore other programs.

# Group types

There are FOUR distinct group patterns. Identify which pattern each requirement is and
emit the correct fields:

## 1. Core / required courses (take ALL listed courses)
Set `required_credits` to the sum of all course units. List every required course.
When the bulletin says "X or Y" for one slot, emit ONE entry with `any_of`:
  {{"any_of": [{{"code": "CHEM 1601", "title": "Principles of General Chemistry I"}}, {{"code": "CHEM 1701", "title": "General Chemistry I"}}], "credits": 3}}

## 2. Credit bucket (take N credits from a department, e.g. "18 units of BIOL 3000+")
Set `required_credits` to the credit target. Set `distribution: true`.
For courses, use ONLY the department code: [{{"code": "BIOL", "title": ""}}].
Do NOT list every possible course — just the department.

## 3. Pick-one list (choose 1 course from a list, e.g. "Advanced Laboratory Course")
Set `required_count: 1`, `required_credits: 0`. List all options as courses.
The student only needs ONE — percentage is based on required_count, not list length.

## 4. Area / breadth requirement (one from each area)
When the bulletin says "at least one course from each of Area A, B, C", emit EACH AREA
as its own SEPARATE group with `required_count: 1`, `required_credits: 0`.
Name each group clearly (e.g. "Area A: Cellular and Molecular Biology").

# Field reference

For each group:
- `name`: short descriptive name
- `required_credits`: total credits needed (0 if count-based)
- `required_count`: number of courses needed (0 if credit-based, 1 for pick-one)
- `courses`: list of course objects: {{"code": "DEPT 1234", "title": "Course Title"}}
- `distribution`: true for credit buckets and area/breadth groups, false for core courses
- `lab_required`: true only if the text explicitly mentions "lab" or "laboratory" requirement
- `lab_options`: list of lab course codes if lab_required is true, else []

# Rules

- Use ONLY course codes from the bulletin text — never substitute or guess codes
- If a credit range is given (e.g. "12-15 credits"), use the minimum
- Copy course titles exactly as listed in the bulletin
- Do NOT mix group types: a "18 units of BIOL 3000+" is a credit bucket (type 2),
  NOT a list of every BIOL 3000+ course
- Return ONLY valid JSON — no commentary, no markdown fences, no ```

# Raw bulletin text

{raw_text}

# Output format

{{
  "program": "full program name from bulletin",
  "school": "Arts & Sciences or Engineering or ...",
  "groups": [
    {{
      "name": "...",
      "required_credits": 0,
      "required_count": 0,
      "courses": [{{"code": "DEPT 1234", "title": "Course Title"}}],
      "distribution": false,
      "lab_required": false,
      "lab_options": []
    }}
  ]
}}
"""


def _parse_with_llm_debug(raw_text: str, program_name: str = "") -> tuple[dict, dict]:
    """Use MiniMax to parse raw bulletin text into structured requirements, with debug info."""
    prompt = EXTRACT_PROMPT.format(raw_text=raw_text[:48000], program_name=program_name or "the program")
    dbg = {
        "parse_prompt_preview": prompt[:800],
        "parse_input_chars": len(raw_text or ""),
    }
    try:
        response = complete(MINIMAX_MODEL, prompt)
        dbg["parse_response_preview"] = (response or "")[:1200]
        # Strip both <think> and <thinking> tags (MiniMax uses the latter)
        response = re.sub(r"<thinking[\s\S]*?</thinking>", "", response, flags=re.IGNORECASE)
        response = re.sub(r"<think>[\s\S]*?</think>", "", response, flags=re.IGNORECASE)
        response = response.replace("```json", "").replace("```", "").strip()
        # Try to extract JSON
        json_start = response.find("{")
        if json_start == -1:
            dbg["parse_error"] = "no_json_object_found"
            return {}, dbg
        json_str = response[json_start:]
        # Handle cases where LLM adds trailing text after JSON
        last_brace = json_str.rfind("}")
        if last_brace != -1:
            json_str = json_str[:last_brace + 1]
        parsed = json.loads(json_str)
        dbg["parse_ok"] = bool(parsed)
        return parsed, dbg
    except (json.JSONDecodeError, Exception) as e:
        dbg["parse_error"] = f"{type(e).__name__}: {e}"
        return {}, dbg


def _parse_with_llm(raw_text: str, program_name: str = "") -> dict:
    """Use MiniMax to parse raw bulletin text into structured requirements."""
    parsed, _dbg = _parse_with_llm_debug(raw_text, program_name=program_name)
    return parsed


def _find_program_node(program_name: str, tree: dict) -> dict | None:
    """Direct tree lookup by exact program name (case-insensitive)."""
    def walk(nodes):
        for node in nodes:
            title = (node.get("title") or "").replace("&#39;", "'").replace("&amp;", "&")
            if title.lower() == program_name.lower():
                return node
            if node.get("nodes"):
                result = walk(node["nodes"])
                if result:
                    return result
        return None
    return walk(tree.get("structure", []))


def _canonical_program_name(program_name: str) -> str:
    """Map a verbose/aliased program name to its canonical bulletin title."""
    matches = extract_programs_from_query(program_name)
    return matches[0] if matches else program_name


def _fetch_program_text(program_name: str, program_type: str | None = None, school: str | None = None) -> str:
    """Use agentic retrieval to collect evidence for a program."""
    lookup = _canonical_program_name(program_name)
    queries = [f"what are the requirements for the {lookup}"]

    best_evidence = ""
    best_len = 0
    for q in queries:
        evidence, _sources, _diag = agentic_collect_evidence(q)
        score = len(evidence or "")
        if score > best_len:
            best_len = score
            best_evidence = evidence or ""

    if not best_evidence.strip():
        raise ValueError(f"Could not find '{program_name}' in bulletin evidence.")
    return _normalize_evidence(best_evidence)


def _fetch_program_text_debug(program_name: str, program_type: str | None = None, school: str | None = None) -> tuple[str, dict]:
    """Debug version of program evidence retrieval with full query/evidence tracing."""
    type_label = program_type if program_type in {"major", "minor"} else "program"
    lookup = _canonical_program_name(program_name)
    queries = [f"what are the requirements for the {lookup}"]

    attempts = []
    best_evidence = ""
    best_len = 0
    best_idx = -1
    best_relevance = 0

    for i, q in enumerate(queries):
        evidence, sources, diag = agentic_collect_evidence(q)
        ev_len = len(evidence or "")
        relevance = 0
        attempts.append({
            "query": q,
            "evidence_chars": ev_len,
            "relevance_score": relevance,
            "evidence_preview": (evidence or "")[:700],
            "sources": [{"title": s.get("title", ""), "tree_id": s.get("tree_id", ""), "page_range": s.get("page_range", "")} for s in (sources or [])[:5]],
            "retriever_diag": diag,
        })
        if ev_len > best_len:
            best_len = ev_len
            best_evidence = evidence or ""
            best_idx = i
            best_relevance = 0

    dbg = {
        "program_name": program_name,
        "program_type": type_label,
        "school": school or "",
        "attempts": attempts,
        "selected_attempt_index": best_idx,
        "selected_evidence_chars": best_len,
        "selected_relevance_score": best_relevance,
    }
    if not best_evidence.strip():
        dbg["failure_stage"] = "retrieval_failed"
        return "", dbg
    dbg["failure_stage"] = ""
    return _normalize_evidence(best_evidence), dbg


def get_program_evidence_debug(
    program_name: str,
    program_type: str | None = None,
    school: str | None = None,
    include_full: bool = False,
) -> tuple[str, dict]:
    """
    Fetch raw requirement evidence without parsing to requirement groups.
    Used by hybrid raw-compare audit mode.
    """
    evidence, dbg = _fetch_program_text_debug(program_name, program_type=program_type, school=school)
    if include_full:
        dbg["selected_evidence_full"] = evidence
        sel = dbg.get("selected_attempt_index", -1)
        attempts = dbg.get("attempts", [])
        if isinstance(sel, int) and 0 <= sel < len(attempts):
            dbg["selected_sources_full"] = attempts[sel].get("sources", [])
    if not evidence.strip():
        raise ValueError(json.dumps({
            "failure_stage": "retrieval_failed",
            "program_name": program_name,
            "debug": dbg,
        }))
    return evidence, dbg


def get_requirements(program_name: str, program_type: str | None = None, school: str | None = None) -> dict:
    """
    Extract structured requirements for a WashU program from the bulletin.

    Uses keyword tree search + MiniMax parsing. Results are cached in memory.

    Args:
        program_name: e.g. "Biology, B.A." or "Computer Science Minor"

    Returns:
        {
          "program": "Biology, B.A.",
          "school": "Arts & Sciences",
          "groups": [
            {
              "name": "Gateway Courses",
              "required_credits": 12,
              "courses": ["BIOL 296", "BIOL 297", "CHEM 111", "CHEM 112"],
              "distribution": false,
              "lab_required": false,
              "lab_options": []
            }
          ]
        }
    """
    canonical = _canonical_program_name(program_name)
    cache_key = f"{canonical}|{program_type or ''}|{school or ''}"
    if cache_key in _cache:
        return _cache[cache_key]

    raw_text = _fetch_program_text(program_name, program_type=program_type, school=school)
    result = _parse_with_llm(raw_text, program_name=canonical)

    if not result or not result.get("groups"):
        # Fallback: try the canonical bulletin title directly (handles cases where
        # the profile program name doesn't appear verbatim in the bulletin but the
        # canonical form does, e.g. "Genomics and Computational Biology Specialization").
        if program_name != canonical:
            try:
                fallback_text = _fetch_program_text(canonical, program_type=program_type, school=school)
                result = _parse_with_llm(fallback_text, program_name=canonical)
            except Exception:
                pass

    if not result or not result.get("groups"):
        raise ValueError(
            f"Failed to extract requirements for '{program_name}'. "
            f"The bulletin may not contain detailed requirements for this program."
        )

    _cache[cache_key] = result
    return result


def get_requirements_debug(program_name: str, program_type: str | None = None, school: str | None = None) -> tuple[dict, dict]:
    """Debug version: returns (requirements, debug_trace)."""
    cache_key = f"{program_name}|{program_type or ''}|{school or ''}"
    if cache_key in _cache:
        return _cache[cache_key], {"cache_hit": True}

    evidence, retr_dbg = _fetch_program_text_debug(program_name, program_type=program_type, school=school)
    if not evidence.strip():
        raise ValueError(json.dumps({
            "failure_stage": "retrieval_failed",
            "program_name": program_name,
            "debug": retr_dbg,
        }))

    result, parse_dbg = _parse_with_llm_debug(evidence, program_name=program_name)
    if not result or not result.get("groups"):
        raise ValueError(json.dumps({
            "failure_stage": "parse_failed",
            "program_name": program_name,
            "debug": {
                "retrieval": retr_dbg,
                "parsing": parse_dbg,
            },
        }))

    _cache[cache_key] = result
    return result, {
        "cache_hit": False,
        "retrieval": retr_dbg,
        "parsing": parse_dbg,
    }


# ── College-level (general education) graduation requirements ─────────────────────────────────────────────

COLLEGE_PARSE_PROMPT = """You are a WashU degree requirements parser. Given raw bulletin text for a college's
general education / graduation requirements, extract all requirement groups.

For each requirement group, identify:
- name: short descriptive name (e.g. "First-Year Writing", "Language Requirement", "Natural Sciences Distribution")
- required_credits: total credits needed (integer), use 0 if only courses required without credit count
- courses: list of course objects with code AND title, e.g. [{{"code": "CWP 1170", "title": "Introduction to College Writing"}}]
  Use the CURRENT course code from the bulletin. Include the course title exactly as listed.
  If only a department is listed (e.g. "any humanities course"), use just the department code: {{"code": "HIST", "title": ""}}
- distribution: boolean — is this a distribution/breadth requirement?
- lab_required: boolean — does this group require a lab?
- lab_options: list of lab course codes if lab_required is true, else []

Also extract:
- program: the college name (e.g. "Arts & Sciences Graduation Requirements")
- school: school name (e.g. "Arts & Sciences", "Engineering")

Rules:
- Include only officially listed distribution categories
- For "any" courses (e.g. "any humanities course"), list the department codes that count (e.g. [{{"code": "AMCS", "title": ""}}, {{"code": "HIST", "title": ""}}])
- Lab requirements: set lab_required=true only if "lab" or "laboratory" appears
- Return ONLY valid JSON — no commentary, no markdown fences

Raw bulletin text:
{raw_text}

Return ONLY valid JSON in this exact format:
{{
  "program": "...",
  "school": "...",
  "groups": [
    {{
      "name": "...",
      "required_credits": 0,
      "courses": [{{"code": "DEPT 1234", "title": "Course Title"}}],
      "distribution": false,
      "lab_required": false,
      "lab_options": []
    }}
  ]
}}
"""

# Cache key for college requirements
_college_cache: dict[str, dict] = {}


def get_college_requirements(school_name: str) -> dict:
    """
    Return the natural-language requirements text for a college's general education requirements.
    Uses the proven chat pipeline (agentic_retrieve) to get accurate bulletin content.

    Returns a dict with "requirements_text", "program", and "school" — the college audit
    then passes this text to the LLM claims pipeline (same as major audit).
    """
    from services.agentic_retriever import agentic_retrieve as _retrieve

    cache_key = school_name
    if cache_key in _college_cache:
        return _college_cache[cache_key]

    school_query_map = {
        "arts-sciences": "What are ALL the college-wide general education requirements that Arts & Sciences students must complete? Include the complete Core Skills requirements (College Writing, Applied Numeracy, Social Contrasts, Writing-Intensive Course) AND all distribution area requirements (Humanities, Natural Sciences & Mathematics, Social Sciences, Language & Cultural Diversity). Do not include major-specific requirements.",
        "engineering": "What are the college-wide general education requirements that ALL Engineering students must complete, regardless of major? List only the distribution requirements and writing requirements.",
        "business": "What are the college-wide general education requirements that ALL Olin Business School students must complete, regardless of major?",
    }
    query = school_query_map.get(school_name.lower(), f"What are the general graduation requirements for {school_name}?")

    result_obj = _retrieve(query)
    requirements_text = result_obj.answer

    school_display_map = {
        "arts-sciences": "Arts & Sciences",
        "engineering": "Engineering",
        "business": "Business",
    }
    school_display = school_display_map.get(school_name.lower(), school_name.title())

    result = {
        "program": f"{school_display} Graduation Requirements",
        "school": school_display,
        "requirements_text": requirements_text,
    }
    _college_cache[cache_key] = result
    return result


def _parse_college_with_llm(raw_text: str, school_hint: str = '') -> dict:
    """Use MiniMax to parse raw bulletin text into college requirement groups."""
    prompt = COLLEGE_PARSE_PROMPT.format(raw_text=raw_text[:48000])
    try:
        response = complete(MINIMAX_MODEL, prompt)
        response = response.replace('<thinking>', '').replace('</thinking>', '').strip()
        json_start = response.find('{')
        if json_start == -1:
            return {}
        json_str = response[json_start:]
        last_brace = json_str.rfind('}')
        if last_brace != -1:
            json_str = json_str[:last_brace + 1]
        return json.loads(json_str)
    except (json.JSONDecodeError, Exception):
        return {}
