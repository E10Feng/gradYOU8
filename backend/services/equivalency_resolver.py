"""
Equivalency Resolver — maps non-standard / legacy course codes to official WashU codes.
Uses a two-layer approach:
  Layer 1 (course_code_map.json): mechanical renumbering (WashU renamed CSE 131 → CSE 1301)
  Layer 2 (equivalencies.json):   semantic judgments (CSE-E81 132 NOT equivalent to CSE 1302)
"""
import json
import os
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(os.getenv("DATA_DIR", "../data"))
_EQUIV_PATH = _DATA_DIR / "equivalencies.json"
_CODE_MAP_PATH = _DATA_DIR / "course_code_map.json"

# In-memory caches
_equiv_cache: Optional[dict] = None
_code_map_cache: Optional[dict] = None


def _load_code_map() -> dict:
    """Load the course code renumbering map (Layer 1). Safe no-op if missing."""
    global _code_map_cache
    if _code_map_cache is not None:
        return _code_map_cache
    if not _CODE_MAP_PATH.exists():
        _code_map_cache = {}
        return {}
    with open(_CODE_MAP_PATH, "r", encoding="utf-8") as f:
        _code_map_cache = json.load(f)
    return _code_map_cache


def _load_equiv() -> dict:
    """Load the semantic equivalency table (Layer 2)."""
    global _equiv_cache
    if _equiv_cache is not None:
        return _equiv_cache
    if not _EQUIV_PATH.exists():
        _equiv_cache = {}
        return {}
    with open(_EQUIV_PATH, "r", encoding="utf-8") as f:
        _equiv_cache = json.load(f)
    return _equiv_cache


def _all_entries() -> dict:
    """Flatten all subject sections in equivalencies.json into a single dict."""
    data = _load_equiv()
    flat = {}
    for subject, entries in data.items():
        if subject.startswith("_"):
            continue
        for code, info in entries.items():
            full_code = f"{subject} {code}" if " " not in code else code
            flat[full_code] = info
    return flat


def _normalize_code(code: str) -> str:
    """Normalize a course code: upper-case, collapse whitespace."""
    return code.upper().strip().replace("\t", " ")


def _code_map_lookup(course_code: str) -> str | None:
    """Layer 1 lookup: return the new code if this is a mechanical renumbering."""
    code_map = _load_code_map()
    mappings = code_map.get("mappings", {})
    return mappings.get(course_code, {}).get("new_code") or mappings.get(_normalize_code(course_code), {}).get("new_code")


def resolve(course_code: str) -> dict:
    """
    Resolve a course code through two layers.

    Layer 1 — mechanical renumbering (course_code_map.json):
      e.g. CHEM 111A → CHEM 1701, CSE 131 → CSE 1301
    Layer 2 — semantic equivalences (equivalencies.json):
      e.g. CSE-E81 132 NOT equivalent to CSE 1302

    Returns:
        {
            "original": "CSE-E81 131",
            "official": "CSE 1301",       # final canonical code, or None
            "equivalent": True,           # True / False / None (unknown)
            "not_equivalent": False,       # True / False / None
            "note": "...",
            "via": "course_code_map" | "equivalencies"
        }
    """
    normalized = _normalize_code(course_code)

    # ── Layer 1: mechanical renumbering ─────────────────────────────────────────
    new_code = _code_map_lookup(course_code)
    if new_code:
        return {
            "original": course_code,
            "official": new_code,
            "equivalent": True,
            "not_equivalent": False,
            "note": None,
            "via": "course_code_map",
        }

    # ── Layer 2: semantic equivalences ─────────────────────────────────────────
    entries = _all_entries()
    if normalized in entries:
        info = entries[normalized]
        official = info.get("official")
        status = info.get("equiv_status", "unknown")
        return {
            "original": course_code,
            "official": official,
            "equivalent": status in ("confirmed", "official_code"),
            "not_equivalent": status == "not_equivalent",
            "note": info.get("note"),
            "via": "equivalencies",
        }

    # Unknown — neither renumbering nor semantic entry
    return {
        "original": course_code,
        "official": None,
        "equivalent": None,
        "not_equivalent": None,
        "note": None,
        "via": None,
    }


def official_code(course_code: str) -> Optional[str]:
    """Return the official WashU code for a course, or None if not equivalent."""
    result = resolve(course_code)
    if result.get("equivalent"):
        return result["official"]
    return None
