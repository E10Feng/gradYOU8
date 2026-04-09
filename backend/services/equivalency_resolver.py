"""
Equivalency Resolver — maps non-standard / legacy course codes to official WashU codes.
Loads equivalencies from data/equivalencies.json.
"""
import json
import os
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(os.getenv("DATA_DIR", "../data"))
_EQUIV_PATH = _DATA_DIR / "equivalencies.json"

# In-memory cache
_equiv_cache: Optional[dict] = None


def _load_equiv() -> dict:
    global _equiv_cache
    if _equiv_cache is not None:
        return _equiv_cache
    if not _EQUIV_PATH.exists():
        return {}
    with open(_EQUIV_PATH, "r", encoding="utf-8") as f:
        _equiv_cache = json.load(f)
    return _equiv_cache


def _all_entries() -> dict:
    """Flatten all subject sections into a single dict keyed by full course code."""
    data = _load_equiv()
    flat = {}
    for subject, entries in data.items():
        if subject.startswith("_"):
            continue
        for code, info in entries.items():
            full_code = f"{subject} {code}" if " " not in code else code
            flat[full_code] = info
    return flat


def resolve(course_code: str) -> dict:
    """
    Resolve a course code.

    Returns:
        {
            "original": "CSE-E81 131",
            "official": "CSE 131",        # None if not equivalent
            "equivalent": True,           # True / False / None (unknown)
            "note": "..."                 # may be absent
        }
    """
    entries = _all_entries()

    # Try exact match first
    if course_code in entries:
        info = entries[course_code]
        official = info.get("official")
        status = info.get("equiv_status", "unknown")
        return {
            "original": course_code,
            "official": official,
            "equivalent": status == "confirmed" or status == "official_code",
            "not_equivalent": status == "not_equivalent",
            "note": info.get("note"),
        }

    return {
        "original": course_code,
        "official": None,
        "equivalent": None,
        "not_equivalent": None,
        "note": None,
    }


def official_code(course_code: str) -> Optional[str]:
    """Return the official WashU code for a course, or None if not equivalent."""
    result = resolve(course_code)
    if result.get("equivalent"):
        return result["official"]
    return None
