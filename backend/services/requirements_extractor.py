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

from pageindex_agent.utils import ChatGPT_API
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
EXTRACT_PROMPT = """You are a WashU degree requirements parser. Given raw bulletin text for a specific program,
extract all requirement groups and return ONLY valid JSON.

For each requirement group, identify:
- name: short descriptive name (e.g. "Gateway Courses", "Upper-Level Biology Electives")
- required_credits: total credits needed for this group (integer)
- courses: list of specific course codes/numbers required (e.g. ["BIOL 296", "BIOL 297"])
- distribution: boolean — is this a distribution/breadth requirement?
- lab_required: boolean — does this group require a lab?
- lab_options: list of lab course codes if lab_required is true, else []

Also extract:
- program: full program name (e.g. "Biology, B.A.")
- school: school name (e.g. "Arts & Sciences", "Engineering")

Rules:
- Only include courses explicitly listed as required in the text
- If a credit range is given (e.g. "12-15 credits"), use the minimum
- lab_required should be true only if the word "lab" or "laboratory" appears in the requirement description
- Return ONLY the JSON — no commentary, no markdown fences

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
      "courses": ["..."],
      "distribution": false,
      "lab_required": false,
      "lab_options": []
    }}
  ]
}}
"""


def _parse_with_llm_debug(raw_text: str) -> tuple[dict, dict]:
    """Use MiniMax to parse raw bulletin text into structured requirements, with debug info."""
    prompt = EXTRACT_PROMPT.format(raw_text=raw_text[:8000])
    dbg = {
        "parse_prompt_preview": prompt[:800],
        "parse_input_chars": len(raw_text or ""),
    }
    try:
        response = ChatGPT_API(MINIMAX_MODEL, prompt)
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


def _parse_with_llm(raw_text: str) -> dict:
    """Use MiniMax to parse raw bulletin text into structured requirements."""
    parsed, _dbg = _parse_with_llm_debug(raw_text)
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
    result = _parse_with_llm(raw_text)

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

    result, parse_dbg = _parse_with_llm_debug(evidence)
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
- courses: list of specific course codes/numbers that satisfy this requirement (e.g. ["CWP 117", "EALC 227"])
- distribution: boolean — is this a distribution/breadth requirement?
- lab_required: boolean — does this group require a lab?
- lab_options: list of lab course codes if lab_required is true, else []

Also extract:
- program: the college name (e.g. "Arts & Sciences Graduation Requirements")
- school: school name (e.g. "Arts & Sciences", "Engineering")

Rules:
- Include only officially listed distribution categories
- For "any" courses (e.g. "any humanities course"), list the department codes that count (e.g. ["AMCS", "HIST", "PHIL", "REL"])
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
      "courses": ["..."],
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
    Extract general education / graduation requirements for a college/school.

    Args:
        school_name: e.g. "arts-sciences", "engineering", "business"

    Returns:
        {
          "program": "Arts & Sciences Graduation Requirements",
          "school": "Arts & Sciences",
          "groups": [
            {
              "name": "First-Year Writing",
              "required_credits": 3,
              "courses": ["CWP 117", "CWP 120"],
              "distribution": false,
              "lab_required": false,
              "lab_options": []
            },
            {
              "name": "Natural Sciences Distribution",
              "required_credits": 6,
              "courses": ["ASTR", "BIOL", "CHEM", "EES", "PHYS"],
              "distribution": true,
              "lab_required": false,
              "lab_options": []
            }
          ]
        }
    """
    cache_key = school_name
    if cache_key in _college_cache:
        return _college_cache[cache_key]

    # Map normalized school name to search terms
    school_search_map = {
        "arts-sciences": [
            "Arts & Sciences graduation requirements",
            "Arts & Sciences general education requirements",
            "College of Arts & Sciences degree requirements",
        ],
        "engineering": [
            "Engineering graduation requirements",
            "School of Engineering degree requirements",
        ],
        "business": [
            "Business school graduation requirements",
            "Olin Business School degree requirements",
        ],
    }

    search_terms = school_search_map.get(school_name.lower(), [f"{school_name} graduation requirements"])
    all_texts = []
    for term in search_terms:
        try:
            evidence, _sources, _diag = agentic_collect_evidence(term)
            if evidence.strip():
                all_texts.append(evidence)
        except Exception:
            continue
    if not all_texts:
        raise ValueError(f"Could not find graduation requirements for '{school_name}' in bulletin.")
    combined_text = "\n\n".join(all_texts[:3])  # keep prompt bounded
    result = _parse_college_with_llm(combined_text, school_name)

    if not result or not result.get("groups"):
        # Return a partial structure rather than failing entirely
        result = {
            "program": f"{school_name.title()} Graduation Requirements",
            "school": school_name.title(),
            "groups": [],
        }

    _college_cache[cache_key] = result
    return result


def _parse_college_with_llm(raw_text: str, school_hint: str = '') -> dict:
    """Use MiniMax to parse raw bulletin text into college requirement groups."""
    prompt = COLLEGE_PARSE_PROMPT.format(raw_text=raw_text[:8000])
    try:
        response = ChatGPT_API(MINIMAX_MODEL, prompt)
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
