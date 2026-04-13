"""
POST /api/audit-full — full degree audit using a 2-step LLM pipeline.

Step A (LLM, cached): extract structured requirement groups from the bulletin via get_requirements()
Step B (LLM):         compare student courses against those groups → structured JSON result
Fallback:             deterministic course-code matching if Step B fails
"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

_BACKEND_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from ..services.requirements_extractor import get_requirements, get_college_requirements
from ..services.equivalency_resolver import resolve, official_code
from ..services.agentic_retriever import agentic_retrieve
from ..services.llm import complete

router = APIRouter(prefix="/api", tags=["audit"])

# ---------------------------------------------------------------------------
# Course tag catalog (from bulletin — WI, SC, AN designations)
# ---------------------------------------------------------------------------

_DATA_DIR = _BACKEND_ROOT.parent / "data"

def _load_course_tags() -> dict:
    path = _DATA_DIR / "course_tags.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

_COURSE_TAGS: dict = _load_course_tags()


def _resolve_tags(course_code: str) -> list[str]:
    """Return A&S IQ tags for a course code, checking both the raw code and equivalencies."""
    code = course_code.strip().upper()
    if code in _COURSE_TAGS:
        return _COURSE_TAGS[code].get("tags", [])
    # Try stripping trailing letter variants (e.g. CHEM 111A → CHEM 111)
    stripped = re.sub(r'[A-Z]$', '', code).strip()
    if stripped in _COURSE_TAGS:
        return _COURSE_TAGS[stripped].get("tags", [])
    return []


def _build_core_skills_context(courses: list[dict]) -> str:
    """
    Pre-resolve Core Skills designations (WI, SC, AN) for the student's courses
    using the bulletin catalog, so the LLM doesn't have to guess.
    CWP courses are identified by code prefix.
    """
    cwp_courses = []
    an_courses = []
    sc_courses = []
    wi_courses = []
    unresolved = []

    for c in courses:
        code = c.get("id", c.get("code", "")).strip().upper()
        title = c.get("title", "")
        label = f"{code} — {title}" if title else code

        if re.match(r'CWP\s', code):
            cwp_courses.append(label)
            continue

        tags = _resolve_tags(code)
        # Also check via equivalency resolver
        if not tags:
            resolved = official_code(code)
            if resolved and resolved != code:
                tags = _resolve_tags(resolved)

        tagged = False
        if 'AN' in tags:
            an_courses.append(label)
            tagged = True
        if 'SC' in tags:
            sc_courses.append(label)
            tagged = True
        if 'WI' in tags:
            wi_courses.append(label)
            tagged = True
        if not tagged and not tags:
            unresolved.append(code)

    lines = ["BULLETIN-VERIFIED Core Skills designations for the student's courses:"]
    lines.append(f"College Writing (CWP): {', '.join(cwp_courses) if cwp_courses else 'none found'}")
    lines.append(f"Applied Numeracy (AN): {', '.join(an_courses) if an_courses else 'none found'}")
    lines.append(f"Social Contrasts (SC): {', '.join(sc_courses) if sc_courses else 'none found'}")
    lines.append(f"Writing-Intensive (WI): {', '.join(wi_courses) if wi_courses else 'none found'}")
    if unresolved:
        lines.append(f"(Could not find bulletin tags for: {', '.join(unresolved[:10])} — use your best judgment for these)")
    lines.append("Use ONLY the above lists to determine Core Skills satisfaction. Do not infer WI/SC/AN from course titles or departments.")
    return "\n".join(lines)


class AuditFullRequest(BaseModel):
    program: str | None = None          # legacy singular
    programs: list[dict] | None = None  # [{name: "...", type: "...", school: "..."}]
    courses: list[dict] | None = None   # [{id: "BIOL 296", title: "...", credits: 3, grade: "A"}]
    student: dict | None = None         # {name, id, school} — from client localStorage
    gpa: float | None = None
    debug: bool = False


# ---------------------------------------------------------------------------
# Course-code utilities (single canonical implementations for this module)
# ---------------------------------------------------------------------------

def _resolve_course(course_code: str) -> tuple[str | None, bool, str]:
    r = resolve(course_code)
    if r.get("equivalent"):
        return r["official"], True, f"{r['official']} (via {course_code})"
    elif r.get("not_equivalent"):
        return None, False, f"{course_code} NOT equivalent — {r.get('note', '')}"
    return None, None, f"{course_code} (not in equivalency table)"


def _normalize_code(code: str) -> str:
    c = (code or "").upper().strip()
    c = c.replace("-", " ").replace("/", " ")
    c = " ".join(c.split())
    c = re.sub(r"^([A-Z&]+)\s+E\d+\s+(\d+[A-Z]?)$", r"\1 \2", c)
    return c


def _code_variants(code: str) -> set[str]:
    """Generate all plausible code variants for matching.

    WashU renumbered 3-digit → 4-digit codes (e.g. CSE 131 → CSE 1310).
    We generate both directions plus intermediate patterns so that a
    student transcript with the old code still matches a requirement
    listing the new code (or vice versa).
    """
    base = _normalize_code(code)
    variants = {base}
    resolved, equiv, _ = _resolve_course(base)
    if equiv is True and resolved:
        variants.add(_normalize_code(resolved))
    m = re.match(r"^([A-Z&]+)\s+(\d{3,4}[A-Z]?)$", base)
    if not m:
        return variants
    dept, num = m.group(1), m.group(2)
    suffix = ""
    if num and num[-1].isalpha():
        suffix = num[-1]
        digits_only = num[:-1]
    else:
        digits_only = num
    if digits_only.isdigit():
        d = int(digits_only)
        if len(digits_only) == 3:
            # 131 → 1310, 1311, 1301 (common renumbering patterns)
            variants.add(f"{dept} {d * 10}{suffix}")
            variants.add(f"{dept} {d * 10 + 1}{suffix}")
            variants.add(f"{dept} {digits_only}0{suffix}")
            variants.add(f"{dept} {digits_only}1{suffix}")
        elif len(digits_only) == 4:
            # 1310 → 131, 1301 → 130
            variants.add(f"{dept} {digits_only[:-1]}{suffix}")
            # Also try dividing by 10
            if d % 10 <= 1:
                variants.add(f"{dept} {d // 10}{suffix}")
    return variants


def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy title comparison."""
    t = (title or "").lower().strip()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return " ".join(t.split())


def _titles_match(title_a: str, title_b: str) -> bool:
    """Check if two course titles are similar enough to be the same course.

    Uses word-overlap: if ≥60% of the shorter title's words appear in the
    longer title, consider it a match.  Ignores common filler words.
    """
    STOP = {"and", "the", "of", "in", "to", "a", "an", "for", "i", "ii", "iii", "iv"}
    a = _normalize_title(title_a)
    b = _normalize_title(title_b)
    if not a or not b:
        return False
    # Exact match after normalization
    if a == b:
        return True
    words_a = set(a.split()) - STOP
    words_b = set(b.split()) - STOP
    if not words_a or not words_b:
        return False
    shorter, longer = (words_a, words_b) if len(words_a) <= len(words_b) else (words_b, words_a)
    overlap = len(shorter & longer)
    return overlap >= max(2, len(shorter) * 0.6)


def _dept_from_code(code: str) -> str:
    """Extract department prefix from a course code like 'BIOL 296' → 'BIOL'."""
    m = re.match(r"^([A-Z&]+)", _normalize_code(code))
    return m.group(1) if m else ""


def _group_dominant_depts(group: dict) -> set[str]:
    """Return department prefixes that dominate this requirement group.

    A dept is "dominant" if it accounts for >=50% of the group's course entries
    (ignoring empty/invalid codes). For small groups (<=3 courses), every listed
    dept counts. Dept-only entries like {"code": "BIOL"} count too.

    Returns an empty set when the group has no course list or mixed <50% depts,
    which disables the guard (so we don't break general distribution groups).
    """
    from collections import Counter
    raw = group.get("courses", []) or []
    depts: list[str] = []
    for r in raw:
        code = r.get("code", "") if isinstance(r, dict) else str(r)
        d = _dept_from_code(code)
        if d:
            depts.append(d)
    if not depts:
        return set()
    if len(depts) <= 3:
        return set(depts)
    counts = Counter(depts)
    total = len(depts)
    return {d for d, n in counts.items() if n / total >= 0.5}


def _is_dept_code(code: str) -> bool:
    """Check if a code is just a department prefix (e.g. 'BIOL', 'HIST') with no number."""
    c = _normalize_code(code)
    return bool(re.match(r"^[A-Z&]+$", c))


def _group_specificity(group: dict) -> tuple[int, int]:
    """Return a sort key for requirement groups: lower = more specific.

    Specificity tiers:
      0 — groups with specific numeric courses (regardless of distribution flag).
          Includes Area A/B/C which have distribution=true but list specific codes.
      1 — mix of specific and dept-only codes
      2 — dept-only or pure distribution bucket (no specific codes)

    Tiebreaker: groups with higher min course level sort after lower-level
    groups at the same tier, so gateway courses claim before advanced electives.
    """
    raw = group.get("courses", []) or []
    reqs = [_normalize_req(r) for r in raw]
    dept_only = [r for r in reqs if _is_dept_code(r["code"])]
    specific = [r for r in reqs if r["code"] and not _is_dept_code(r["code"])]

    if specific and not dept_only:
        tier = 0  # all specific courses (Area A/B/C, lab lists, core reqs)
    elif dept_only and specific:
        tier = 1  # mix of specific + dept-only
    else:
        tier = 2  # dept-only / pure distribution bucket

    min_lvl = 0
    for r in specific:
        lvl = _course_level(r["code"])
        if lvl > min_lvl:
            min_lvl = lvl

    return (tier, min_lvl)


def _infer_min_level(group: dict) -> int:
    """Return the minimum course level enforced for this requirement group.

    Returns 3000 if the group name signals upper-division work, 5000 for graduate,
    otherwise 0 (no filter). Also checks whether any specific course code listed
    in the group is 3000 or above.
    """
    name_words = set(group.get("name", "").lower().split())
    if name_words & {"upper", "advanced", "upper-level", "upperlevel"}:
        return 3000
    if name_words & {"graduate", "5000", "5000+"}:
        return 5000
    # Check specific course codes listed in the group
    raw = group.get("courses", []) or []
    for r in raw:
        code = r.get("code", "") if isinstance(r, dict) else str(r)
        lvl = _course_level(code)
        if lvl >= 3000:
            return 3000
    return 0


def _course_level(code: str) -> int:
    """Extract course number level: 'BIOL 3200' → 3000, 'CSE 131' → 100."""
    m = re.match(r"^[A-Z&]+\s+(\d+)", _normalize_code(code))
    if not m:
        return 0
    num = int(m.group(1))
    if num < 100:
        return num * 10
    if num < 1000:
        return (num // 100) * 100
    return (num // 1000) * 1000


def _course_number(code: str) -> int:
    """Return the raw course number for threshold comparisons ('BIOL 3240' → 3240)."""
    m = re.search(r'\d+', (code or "").split()[-1] if code else "")
    return int(m.group()) if m else 0


def _normalize_req(raw) -> dict:
    """Normalize a requirement entry to {code, title, credits} regardless of format.

    Handles:
      - Old format: plain string like "CSE 131"
      - New format: dict like {"code": "CSE 1310", "title": "Intro to CS", "credits": 3}
      - any_of slot: dict like {"any_of": [{"code": "...", ...}, ...], "credits": 3}
        Returns {"code": "", "any_of": [...], "title": "", "credits": N}.
    """
    if isinstance(raw, dict):
        if "any_of" in raw:
            return {"code": "", "any_of": raw["any_of"], "title": "", "credits": raw.get("credits", 3)}
        return {"code": raw.get("code", ""), "title": raw.get("title", ""), "credits": raw.get("credits", 3)}
    return {"code": str(raw), "title": ""}


def _audit_group(student_courses: list[dict], group: dict, claimed: set[str] | None = None) -> dict:
    """Deterministic course-code matching for one requirement group.

    Handles three types of requirements:
    1. Specific courses: code matching with equivalency + renumbering variants
    2. Department-only codes (e.g. 'BIOL'): any course from that department counts
    3. Distribution groups: match by department prefix when group.distribution=True

    When code matching fails for a specific course, falls back to title-based
    fuzzy matching (handles course renumbering where codes changed but titles
    stayed the same, e.g. CSE 131 → CSE 1310 "Intro to Computer Science").
    """
    raw_courses = group.get("courses", [])
    required_reqs = [_normalize_req(r) for r in raw_courses]
    required_credits = group.get("required_credits", 0)
    is_distribution = group.get("distribution", False)

    # Derive dominant departments for this group — used to guard Pass 1.
    # Opt-out when empty (mixed cross-dept groups).
    dominant_depts = _group_dominant_depts(group)

    # Minimum course level enforced for this group. Used to block 2000-level
    # student courses from matching "Upper-Level" elective groups.
    min_level = _infer_min_level(group)

    # Pre-compute student course metadata
    student_meta: dict[str, dict] = {}
    for c in student_courses:
        code = c.get("id", "")
        student_meta[code] = {
            "resolved": _resolve_course(code),
            "variants": _code_variants(code),
            "dept": _dept_from_code(code),
            "level": _course_level(code),
            "title": c.get("title", ""),
        }

    satisfied: list[dict] = []       # [{code, title, note?}]
    satisfied_labels: list[str] = []  # display strings for backward compat
    satisfied_credits = 0
    satisfied_set: set[str] = set()
    # Track which requirement codes have been satisfied at the CODE level
    # (independent of credit accumulation). This prevents a requirement from
    # appearing in remaining just because satisfied_credits < required_credits
    # when the code actually matched via equivalency resolution.
    satisfied_req_codes: set[str] = set()
    claimed = claimed if claimed is not None else set()

    def _add_satisfied(sc: dict, note: str = "", req_code: str = ""):
        """Record a student course as satisfying a requirement."""
        sc_code = sc.get("id", "")
        sc_title = sc.get("title", "")
        label = note if note else sc_code
        satisfied.append({"code": sc_code, "title": sc_title, "note": note, "credits": sc.get("credits", 3)})
        satisfied_labels.append(label)
        satisfied_set.add(sc_code)
        if req_code:
            satisfied_req_codes.add(_normalize_code(req_code))
        return sc.get("credits", 3)

    # Separate department-only from specific course requirements.
    # any_of slots are identified from raw courses BEFORE normalization (since
    # _normalize_req strips the any_of key). We keep them as-is (raw dicts).
    raw_courses = group.get("courses", []) or []
    any_of_reqs_raw = [r for r in raw_courses if isinstance(r, dict) and "any_of" in r]
    # Normalize everything else
    required_reqs = [_normalize_req(r) for r in raw_courses]
    dept_reqs = [r for r in required_reqs if _is_dept_code(r["code"])]
    specific_reqs = [r for r in required_reqs if r["code"] and not _is_dept_code(r["code"])]
    # any_of slots: normalized shape still has .any_of; use the raw version for
    # the alternatives list since _normalize_req would preserve it.
    any_of_reqs = [r for r in required_reqs if r.get("any_of")]

    # A credit-bucket group accumulates credits from a broad department pool.
    # Courses that satisfy other specific groups (lab, Area A/B/C) should still
    # contribute credits here — skip the `claimed` check in Pass 1/3.
    # A group is a credit-bucket when it has a credit target AND either:
    #   - only dept-only codes (e.g. {"code": "BIOL"})
    #   - distribution: true (even if LLM listed specific example codes)
    allow_shared = (required_credits > 0) and (is_distribution or (bool(dept_reqs) and not specific_reqs))

    # ── Pass any_of: first matching alternative satisfies the slot ───────────────
    # Each any_of slot contributes at most 1 course to satisfied and 0 to remaining.
    # NOTE: We do NOT apply the min_level guard here. The LLM embeds specific
    # alternative courses (some may be 2000-level) in any_of slots, and the level
    # filter is meant for broad distribution buckets — not for fixed alternatives.
    for req in any_of_reqs:
        alternatives = req["any_of"] or []
        for alt in alternatives:
            alt_code = alt.get("code", "") if isinstance(alt, dict) else str(alt)
            if not alt_code or _is_dept_code(alt_code):
                continue
            alt_variants = _code_variants(_normalize_code(alt_code))
            alt_dept = _dept_from_code(alt_code)
            for sc in student_courses:
                sc_code = sc.get("id", "")
                if sc_code in satisfied_set or sc_code in claimed:
                    continue
                # any_of alternatives are pre-specified by the LLM — do NOT restrict
                # by dominant_depts or min_level. The alternatives themselves encode
                # the appropriate level/scope for this slot.
                meta = student_meta.get(sc_code, {"resolved": (None, None, ""), "variants": set(), "dept": ""})
                resolved, equiv, note = meta["resolved"]
                sc_variants: set[str] = meta["variants"]
                if equiv is True and resolved and _normalize_code(resolved) in alt_variants:
                    satisfied_credits += _add_satisfied(sc, note, req_code=alt_code)
                    break
                elif sc_variants.intersection(alt_variants):
                    note_text = note if (equiv is True and resolved) else f"{sc_code} (≈ {alt_code})"
                    satisfied_credits += _add_satisfied(sc, note_text, req_code=alt_code)
                    break
            if sc_code in satisfied_set:
                break

    # Pass 1: Match specific required courses by code variants + equivalency
    unmatched_reqs: list[dict] = []
    for req in specific_reqs:
        req_code = req["code"]
        req_variants = _code_variants(_normalize_code(req_code))
        matched = False
        for sc in student_courses:
            sc_code = sc.get("id", "")
            if sc_code in satisfied_set:
                continue
            if not allow_shared and sc_code in claimed:
                continue
            meta = student_meta.get(sc_code, {"resolved": (None, None, ""), "variants": set(), "dept": ""})
            sc_dept = meta.get("dept", _dept_from_code(sc_code))
            # Department-consistency guard: if the group is dominated by one or more
            # departments, reject student courses from other departments even if a
            # code variant accidentally matches.
            if dominant_depts and sc_dept not in dominant_depts:
                continue
            # Level guard: for groups that require upper-division work, reject
            # lower-level student courses even if a code variant matches.
            if min_level and meta.get("level", 0) < min_level:
                continue
            resolved, equiv, note = meta["resolved"]
            sc_variants: set[str] = meta["variants"]
            # A not_equivalent course must never satisfy any requirement, even via
            # code-variant intersection. CSE-E81 132 is not equivalent to CSE 1302.
            if equiv is False:
                continue
            if equiv is True and resolved and _normalize_code(resolved) in req_variants:
                satisfied_credits += _add_satisfied(sc, note, req_code=req_code)
                matched = True
                break
            elif sc_variants.intersection(req_variants):
                satisfied_credits += _add_satisfied(sc, "", req_code=req_code)
                matched = True
                break
        if not matched:
            unmatched_reqs.append(req)

    # Pass 2: Title-based fallback for unmatched requirements
    still_unmatched: list[dict] = []
    for req in unmatched_reqs:
        req_title = req.get("title", "")
        req_dept = _dept_from_code(req["code"])
        matched = False
        if req_title:
            for sc in student_courses:
                sc_code = sc.get("id", "")
                if sc_code in satisfied_set or sc_code in claimed:
                    continue
                meta = student_meta.get(sc_code, {})
                # Skip courses explicitly marked not_equivalent — title similarity
                # must not override semantic judgments (e.g. CSE-E81 132 is not
                # equivalent to CSE 1302 even though both contain "Introduction").
                resolved_fallback, equiv_fallback, _ = meta.get("resolved", (None, None, ""))
                if equiv_fallback is False:
                    continue
                sc_dept = meta.get("dept", _dept_from_code(sc_code))
                sc_title = meta.get("title", sc.get("title", ""))
                if sc_dept == req_dept and _titles_match(req_title, sc_title):
                    satisfied_credits += _add_satisfied(sc, f"{sc_code} (≈ {req['code']})", req_code=req["code"])
                    matched = True
                    break
        if not matched:
            still_unmatched.append(req)

    # Match department-only / distribution requirements
    dept_codes_list = [r["code"] for r in dept_reqs]
    specific_codes_list = [r["code"] for r in specific_reqs]
    if dept_codes_list or is_distribution:
        valid_depts = set()
        for code in dept_codes_list:
            valid_depts.add(_normalize_code(code))
        if is_distribution and not valid_depts and specific_codes_list:
            for code in specific_codes_list:
                d = _dept_from_code(code)
                if d:
                    valid_depts.add(d)

        # Safety: intersect with dominant depts so Pass 3 can't silently expand scope
        # past what the group actually covers.
        if dominant_depts and valid_depts:
            valid_depts = valid_depts & dominant_depts

        if valid_depts and required_credits > 0:
            for sc in student_courses:
                if satisfied_credits >= required_credits:
                    break
                sc_code = sc.get("id", "")
                if sc_code in satisfied_set:
                    continue
                # Credit-bucket groups allow courses already claimed by other groups
                if not allow_shared and sc_code in claimed:
                    continue
                meta = student_meta.get(sc_code, {})
                sc_dept = meta.get("dept", _dept_from_code(sc_code))
                if sc_dept in valid_depts:
                    # Reject lower-level courses in upper-division groups.
                    if min_level and meta.get("level", 0) < min_level:
                        continue
                    satisfied_credits += _add_satisfied(sc)

    # Compute remaining with titles for display.
    # any_of slots are handled specially: satisfied → nothing to remaining;
    # unsatisfied → contribute the primary (first) alternative's code.
    # A requirement code is satisfied if its normalized form appears in either
    # satisfied_req_codes (code-level match, independent of credit values) OR
    # in the note of any satisfied entry (equivalency chain display).
    remaining: list[dict] = []
    for req in required_reqs:
        # any_of slots never appear in remaining once any student course satisfied them
        if req.get("any_of"):
            continue
        code = req["code"]
        code_norm = _normalize_code(code)
        satisfied_by_code = code_norm in satisfied_req_codes
        satisfied_by_note = any(
            code_norm in (_normalize_code(s.get("note", "") or ""))
            for s in satisfied
        )
        if not (satisfied_by_code or satisfied_by_note):
            remaining.append({"code": code, "title": req.get("title", ""), "credits": req.get("credits", 3)})
    remaining_labels = [r["code"] for r in remaining]
    num_required = len(required_reqs)
    num_satisfied = len(satisfied)

    # Use credit-based percent when we have credit targets; fall back to course-count;
    # use required_count when credits are 0 (e.g. "one course from each area" groups).
    required_count = int(group.get("required_count", 0) or 0)

    # If all required courses are code-matched (even if credits don't accumulate due to
    # LLM-extraction errors), bump percent to 100 so the group shows green.
    all_req_codes_satisfied = all(
        (_normalize_code(r["code"]) in satisfied_req_codes) or r.get("any_of")
        for r in required_reqs
        if r["code"] and not _is_dept_code(r["code"])
    )

    if all_req_codes_satisfied and required_reqs:
        percent = 100
    elif required_credits > 0:
        percent = min(100, int((satisfied_credits / required_credits) * 100))
    elif required_count > 0:
        percent = min(100, int((min(num_satisfied, required_count) / required_count) * 100))
    elif num_required > 1 and num_satisfied >= 1 and required_credits == 0 and required_count == 0:
        # "Pick one" inference: group lists many options (e.g. 15 possible lab
        # courses) but you only need one. Once any course matches, it's 100%.
        percent = 100
    elif num_required > 0:
        percent = int((num_satisfied / num_required) * 100)
    else:
        percent = 100

    if percent >= 100:
        status = "SATISFIED"
    elif percent > 0:
        status = "PARTIAL"
    else:
        status = "MISSING"

    # Bug 2 fix: when the group is fully satisfied, clear remaining — any
    # unmet alternatives are by definition not required once the group is done.
    if status == "SATISFIED":
        remaining = []
        remaining_labels = []

    return {
        "name": group.get("name", ""),
        "status": status,
        "percent": min(percent, 100),
        "satisfied": satisfied_labels,
        "satisfied_details": satisfied,
        "remaining": remaining_labels,
        "remaining_details": remaining,
        "credit_progress": f"{satisfied_credits}/{required_credits}",
    }


# ---------------------------------------------------------------------------
# Program-level fallback helpers for Biology GCB
# (used when LLM extraction misses Area A/B/C or Specialization CSE groups)
# ---------------------------------------------------------------------------

def _area_ab_c_fallback(student_courses):
    """Check student's BIOL 3000+ courses against known Area A/B/C mappings for GCB.

    Returns {area_name: student_course_code} for each area that is satisfied.
    GCB bulletin: BIOL 3240 → Area A, BIOL 3057 → Area B, BIOL 4181 → Area C.
    """
    AREA_A = {"BIOL 3240", "BIOL 3340", "BIOL 3371", "BIOL 3481", "BIOL 3490",
              "BIOL 4240", "BIOL 4242", "BIOL 4345", "BIOL 4492", "BIOL 4510"}
    AREA_B = {"BIOL 3057", "BIOL 3151", "BIOL 3280", "BIOL 3411", "BIOL 3421",
              "BIOL 3422", "BIOL 3424", "BIOL 4026", "BIOL 4030", "BIOL 4071",
              "BIOL 4072", "BIOL 4381"}
    AREA_C = {"BIOL 3220", "BIOL 3221", "BIOL 3470", "BIOL 3494", "BIOL 3501",
              "BIOL 3700", "BIOL 3810", "BIOL 4181", "BIOL 4182", "BIOL 4183",
              "BIOL 4195", "BIOL 4197", "BIOL 4720"}
    AREAS = {"Area A: Cellular & Molecular": AREA_A,
             "Area B: Organismal Biology": AREA_B,
             "Area C: Evolution, Ecology & Population": AREA_C}

    found: dict[str, str] = {}
    for sc in student_courses:
        code = sc.get("id", "")
        resolved, equiv, _ = _resolve_course(code)
        check_codes = {code, resolved} if equiv is True else {code}
        for area_name, area_set in AREAS.items():
            if area_name in found:
                continue
            for c in check_codes:
                if c and _normalize_code(c) in {_normalize_code(ac) for ac in area_set}:
                    found[area_name] = code
                    break
    return found


def _spec_cse_fallback(student_courses, claimed):
    """Check student's courses against GCB specialization CSE requirements.

    GCB requires CSE 1301 and CSE 2407 (or equivalent via course_code_map.json).
    Returns list of {req, sc} dicts for matched courses.
    """
    matched: list[dict] = []
    for sc in student_courses:
        if sc.get("id") in claimed:
            continue
        resolved, equiv, _ = _resolve_course(sc.get("id", ""))
        if equiv is True and resolved:
            nc = _normalize_code(resolved)
            if nc == "CSE 1301":
                matched.append({"req": "CSE 1301", "sc": sc.get("id", "")})
            elif nc == "CSE 2407":
                matched.append({"req": "CSE 2407", "sc": sc.get("id", "")})
    return matched


def _deterministic_audit(program_name: str, requirements: dict, student_courses: list[dict]) -> dict:
    """Fallback: pure code-matching, no LLM comparison call."""
    groups_results: list[dict] = []
    total_pct = 0
    claimed: set[str] = set()
    groups = list(requirements.get("groups", []))
    # Run most-specific groups first so they claim their courses before
    # broad elective buckets see them. Tiebreaker: lower-level first.
    groups.sort(key=_group_specificity)
    for group in groups:
        result = _audit_group(student_courses, group, claimed)
        # Lock in every matched course so later groups can't double-count it.
        for detail in result.get("satisfied_details", []):
            code = detail.get("code", "")
            if code:
                claimed.add(code)
        groups_results.append(result)
        total_pct += result["percent"]

    # ── PATCH: Area A/B/C fallback ────────────────────────────────────────────
    # If no Area groups were extracted (LLM missed them), try direct code match.
    # Restrict to Biology programs (Arts & Sciences) only.
    _prog_lower = program_name.lower()
    is_biology = any(kw in _prog_lower for kw in ["biology", "computational biology", "genomics"])
    if is_biology:
        area_fallback = _area_ab_c_fallback(student_courses)
        for area_name, sc_code in area_fallback.items():
            if sc_code in claimed:
                continue
            groups_results.append({
                "name": area_name,
                "status": "SATISFIED",
                "percent": 100,
                "satisfied": [sc_code],
                "satisfied_details": [{"code": sc_code, "title": "", "note": "Area match", "credits": 3}],
                "remaining": [],
                "remaining_details": [],
                "credit_progress": "1/1",
            })
            total_pct += 100
            claimed.add(sc_code)

    # ── PATCH: Specialization CSE fallback ─────────────────────────────────────
    # Only for Biology programs that may have GCB-style specialization CSE.
    # Restrict to avoid appending a spurious "Specialization CS" group to
    # unrelated programs (e.g. a CS minor) when the student happened to take CSE 1301.
    if is_biology:
        spec_cse = _spec_cse_fallback(student_courses, claimed)
        if spec_cse:
            # Avoid double-counting if a CSE group already matched these
            already_covered = {
                _normalize_code(d.get("code", ""))
                for gr in groups_results
                for d in gr.get("satisfied_details", [])
            }
            new_spec = [m for m in spec_cse if _normalize_code(m["req"]) not in already_covered]
            if new_spec:
                for m in new_spec:
                    claimed.add(m["sc"])
                n = len(new_spec)
                groups_results.append({
                    "name": "Specialization Computer Science",
                    "status": "SATISFIED" if n >= 2 else "PARTIAL",
                    "percent": 100 if n >= 2 else 50,
                    "satisfied": [f"{m['req']} (via {m['sc']})" for m in new_spec],
                    "satisfied_details": [{"code": m["sc"], "title": "", "note": f"{m['req']} (via {m['sc']})", "credits": 3} for m in new_spec],
                    "remaining": [] if n >= 2 else ["CSE 1302"],
                    "remaining_details": [] if n >= 2 else [{"code": "CSE 1302", "title": "Object-Oriented Software Development Laboratory", "credits": 3}],
                    "credit_progress": f"{n}/2",
                })
                total_pct += (100 if n >= 2 else 50)

    n = len(groups_results)
    return {
        "program": program_name,
        "extracted_program": requirements.get("program", program_name),
        "school": requirements.get("school", ""),
        "overall_percent": int(total_pct / n) if n else 0,
        "groups": groups_results,
        "notes": ["Used deterministic course-matching (LLM comparison unavailable)."],
        "audit_mode": "deterministic_fallback",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_course_codes(profile: dict) -> list[dict]:
    courses: list[dict] = []
    for sem in profile.get("semesters", []):
        for c in sem.get("courses", []):
            courses.append({
                "id": c.get("code", c.get("id", "")),
                "title": c.get("title", ""),
                "credits": c.get("credits", 3),
                "grade": c.get("grade", ""),
            })
    for c in profile.get("courses", []):
        if c not in courses:
            courses.append(c)
    return courses


def _sse_audit(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


_COLLEGE_AUDIT_PROMPT = """You are a college graduation requirements auditor for Washington University in St. Louis.
Given the college's general education requirements and a student's completed courses, determine which requirements are satisfied.

{equivalency_context}

{core_skills_context}

College general education requirements for {prog_name}:
{requirements_text}

{courses_text}

Return a JSON object with this exact structure:
{{
  "program": "{prog_name}",
  "school": "{school}",
  "overall_percent": <0-100>,
  "groups": [
    {{
      "name": "requirement area name (e.g. Humanities, Natural Sciences, Writing)",
      "status": "SATISFIED" or "PARTIAL" or "MISSING",
      "percent": <0-100>,
      "satisfied": ["COURSE_CODE — Title", ...],
      "remaining": ["description of what's still needed"],
      "credit_progress": "X/Y credits" or ""
    }}
  ]
}}

Rules:
- Create ONLY the groups that are explicitly listed in the college requirements — typically 8-9 groups: the 4 Core Skills groups PLUS the distribution area groups. Do NOT create groups for individual courses.
- ONLY include courses from the student's completed courses list in satisfied — NEVER invent courses
- Apply ALL equivalencies from the table above (e.g. CWP 117 = CWP 1507 for Writing)

Core Skills groups (each requires 3 units / 1 course):
  * College Writing: use ONLY the CWP courses listed in the BULLETIN-VERIFIED section above
  * Applied Numeracy: use ONLY the AN courses listed in the BULLETIN-VERIFIED section above
  * Social Contrasts: use ONLY the SC courses listed in the BULLETIN-VERIFIED section above
  * Writing-Intensive: use ONLY the WI courses listed in the BULLETIN-VERIFIED section above
  * For any course marked "could not find bulletin tags", you may use your best judgment based on title/department

Distribution area groups (each requires 9 units / 3 courses minimum, except LCD which requires 9-12 units):
  * Humanities: literature, languages, philosophy, history, art, music, religion, classics, cultural studies
  * Natural Sciences & Mathematics: BIOL, CHEM, PHYSICS, MATH, SDS, CSE, EES, ASTR, statistics
  * Social & Behavioral Sciences: economics, psychology, sociology, anthropology, political science, social work
  * Language & Cultural Diversity: foreign language courses, global studies, cross-cultural courses

Overlap rules:
- Core Skills courses CAN also count toward a distribution area (e.g. a WI course in Humanities counts for both Writing-Intensive and Humanities)
- A course can satisfy AT MOST ONE distribution area (not counted in multiple distribution areas)
- percent for each group = (credits_earned / required_credits) * 100, capped at 100
- overall_percent = average of all group percents
- Return ONLY valid JSON — no markdown fences, no commentary"""


# ---------------------------------------------------------------------------
# Per-program audit: LLM-based pipeline
# ---------------------------------------------------------------------------

_LLM_MODEL = os.getenv("AUDIT_LLM_MODEL", "gemini-3.1-flash-lite-preview")

_EQUIVALENCY_CONTEXT = """IMPORTANT — WashU legacy course code equivalencies:
- CSE-E81 131 = CSE 1301 (Introduction to Computer Science)
- CSE-E81 132 = CSE 1302 (Introduction to Computer Engineering)
- CSE-E81 247 = CSE 2407 (Data Structures and Algorithms)
- CSE-E81 240 = CSE 2400 (Logic and Discrete Mathematics)
- CHEM 111A = CHEM 1701 (General Chemistry I)
- CHEM 112A = CHEM 1711 (General Chemistry II)
- CHEM 151 = CHEM 1721 (General Chemistry Lab I)
- CHEM 152 = CHEM 1731 (General Chemistry Lab II)
- CHEM 261 = CHEM 2611 (Organic Chemistry I With Lab)
- CHEM 262 = CHEM 2621 (Organic Chemistry II With Lab)
- PHYSICS 191 = PHYSICS 1740 (Physics I)
- PHYSICS 192 = PHYSICS 1760 (Physics II)
- PHYSICS 191L = PHYSICS 1741 (Physics I Lab)
- PHYSICS 192L = PHYSICS 1761 (Physics II Lab)
- MATH 309 = MATH 2330 (Matrix Algebra)
- SDS 3211 = SDS 3200 (Statistics for Data Science)
Treat legacy codes as equivalent to the new codes when matching requirements."""


def _format_courses_text(courses: list[dict]) -> str:
    lines = ["Student's completed courses:"]
    for c in courses:
        cid = c.get("id", c.get("code", ""))
        title = c.get("title", "")
        credits = c.get("credits", 0)
        grade = c.get("grade", "")
        lines.append(f"- {cid}: {title} ({credits} cr, {grade})")
    return "\n".join(lines)




# ---------------------------------------------------------------------------
# Option B: LLM Claims → Deterministic Verification
# ---------------------------------------------------------------------------

_CLAIMS_PROMPT = """You are a degree requirements interpreter for Washington University in St. Louis.
Given the program requirements and the student's completed courses, generate structured
CLAIMS about how each course satisfies each requirement. Do NOT produce a final audit —
produce only claims that can be independently verified.

{equivalency_context}

Requirements for {prog_name}:
{requirements_text}

Student's completed courses:
{courses_text}

Output a JSON object with two keys: "claims" (list of claims) and "group_interpretations" (list of group metadata).

Claim types:
- "satisfies_bucket": a course satisfies a credit bucket (e.g. "18 credits of BIOL 3000+")
- "satisfies_area": a course satisfies one of Area A/B/C
- "satisfies_lab": a course satisfies the advanced lab requirement
- "satisfies_specific": a course satisfies a named specific course requirement (not a bucket)
- "satisfies_or_slot": a course satisfies one side of an OR group
- "unmatched_slot": no student course satisfies this requirement slot

Each claim must include:
- type: the claim type
- student_course: the student's actual course code (e.g. "CSE-E81 131")
- group_name: the requirement group this applies to
- credits: credit value of the student course (from their transcript)
- explanation: one sentence explaining why this is a valid match

For "unmatched_slot" claims:
- type: "unmatched_slot"
- group_name: the group
- slot_description: the full text of the unmet slot (e.g. "MATH 2130 OR MATH 3020 OR SDS 2020")
- explanation: why no match was found

For each group in the requirements, include a group_interpretation with:
- group_name
- type: "credit_bucket" | "specific_courses" | "area" | "lab" | "pick_one" | "or_slot_group"
- target_credits (for credit buckets, else 0)
- specific_items (list of specific course codes required)
- min_level: REQUIRED for bucket groups — integer course level (e.g. 3000 for 3000+ level, 0 for no level filter)
- allowed_departments: list of department prefixes allowed (e.g. ["BIOL"]) — empty list means any department
- explicitly_excluded: list of specific course codes that do NOT count even if they match the level/dept — empty list if nothing excluded

Return ONLY valid JSON — no markdown fences, no commentary."""


def _load_course_map() -> dict:
    """Load mechanical renumbering mappings."""
    try:
        path = Path(__file__).parent.parent / "data" / "course_code_map.json"
        with open(path) as f:
            data = json.load(f)
        return data.get("mappings", {})
    except Exception:
        return {}


def _load_equivalencies() -> dict:
    """Load semantic equivalencies."""
    try:
        path = Path(__file__).parent.parent / "data" / "equivalencies.json"
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _resolve_code(code: str, course_map: dict, equivalencies: dict) -> tuple[str, bool]:
    """
    Resolve a student course code to its official bulletin code.
    Returns (resolved_code, is_legacy_resolved).
    """
    # Direct check in course_code_map
    if code in course_map:
        return course_map[code]["new_code"], True

    # Check equivalencies.json semantic entries
    for dept, dept_data in equivalencies.items():
        if isinstance(dept_data, dict) and code in dept_data:
            entry = dept_data[code]
            official = entry.get("official")
            status = entry.get("equiv_status", "")
            if status == "not_equivalent":
                return code, False
            if official:
                return official, True

    # Strip common suffixes
    normalized = re.sub(r"-E\d+", "", code)
    if normalized != code and normalized in course_map:
        return course_map[normalized]["new_code"], True

    return code, False


def _verify_claims(claims: list[dict], courses: list[dict], course_map: dict, equivalencies: dict) -> tuple[list[dict], list[dict]]:
    """
    Verify each claim deterministically against the student's actual transcript.
    Returns (verified_claims, rejected_claims).
    """
    # Build a lookup: canonical student course -> course data
    student_courses = {}  # canonical code -> course dict
    for c in courses:
        raw_code = c.get("id", c.get("code", ""))
        resolved, _ = _resolve_code(raw_code, course_map, equivalencies)
        # Store by both raw and resolved
        student_courses[raw_code] = c
        student_courses[resolved] = c

    verified = []
    rejected = []

    for claim in claims:
        ctype = claim.get("type", "")

        if ctype in ("satisfies_bucket", "satisfies_area", "satisfies_lab", "satisfies_specific", "satisfies_or_slot"):
            student_code = claim.get("student_course", "")
            credits = claim.get("credits", 0)

            # Step 1: Can we trace this to the student's transcript?
            resolved, was_legacy = _resolve_code(student_code, course_map, equivalencies)
            if resolved not in student_courses and student_code not in student_courses:
                claim["reject_reason"] = f"course_not_in_transcript: {student_code} (resolved: {resolved})"
                rejected.append(claim)
                continue

            # Step 2: For buckets — verify department and level
            if ctype == "satisfies_bucket":
                interp = claim.get("bucket_interpretation") or {}

                # Support flat group_interpretation fields (min_level, allowed_departments,
                # explicitly_excluded at top level) and also nested bucket_params for
                # backwards compatibility
                raw_interp = interp.get("bucket_params") or interp

                # If no interpretation attached, try to infer from the group name
                # e.g., "BIOL 3000+ Level Courses" → min_level 3000, allowed_depts ["BIOL"]
                if not raw_interp or raw_interp.get("min_level") is None:
                    gn = claim.get("group_name", "")
                    # Try to extract "DEPT 3000+" pattern from group name
                    m = re.match(r'^([A-Z&]+)\s+(\d+)\+\s+', gn)
                    if m:
                        raw_interp = {
                            "min_level": int(m.group(2)),
                            "allowed_departments": [m.group(1)],
                            "explicitly_excluded": [],
                        }
                    else:
                        raw_interp = {"min_level": 0, "allowed_departments": [], "explicitly_excluded": []}

                min_level = raw_interp.get("min_level")
                allowed_depts = raw_interp.get("allowed_departments") or []
                excluded = raw_interp.get("explicitly_excluded") or []

                # If min_level is None, the LLM didn't specify bucket constraints —
                # conservatively reject (the group interpretation was incomplete)
                if min_level is None:
                    claim["reject_reason"] = "bucket_interpretation_missing_min_level"
                    rejected.append(claim)
                    continue

                level = _course_number(resolved)
                dept = _dept_from_code(resolved)

                if min_level > 0 and level < min_level:
                    claim["reject_reason"] = f"level_too_low: {resolved} is {level}, need {min_level}+"
                    rejected.append(claim)
                    continue
                if allowed_depts and dept not in allowed_depts:
                    claim["reject_reason"] = f"wrong_department: {dept} not in {allowed_depts}"
                    rejected.append(claim)
                    continue
                if resolved in excluded or student_code in excluded:
                    claim["reject_reason"] = f"explicitly_excluded: {resolved}"
                    rejected.append(claim)
                    continue

            # Step 3: Verify credits match the transcript
            transcript_course = student_courses.get(resolved) or student_courses.get(student_code)
            if transcript_course:
                transcript_credits = transcript_course.get("credits", 0)
                if credits != transcript_credits:
                    # Adjust to what the transcript says
                    claim["credits"] = transcript_credits

            verified.append(claim)

        elif ctype == "unmatched_slot":
            # For unmatched slots, verify that no student course could have matched
            slot = claim.get("slot_description", "")
            # Parse OR options from slot text
            # Handle both "CSE 2400" and "MATH 1510: Course Name (3 units)" formats
            opts = re.findall(r'([A-Z]{2,}\s*\d+\w*)', slot)
            if not opts:
                # Try "DEPT NUM: Name" pattern — extract dept+num before the colon
                opts = re.findall(r'([A-Z]{2,}\s*\d+\w*)\s*:', slot)
            any_match = False
            for opt in opts:
                resolved_opt, _ = _resolve_code(opt, course_map, equivalencies)
                if resolved_opt in student_courses or opt in student_courses:
                    any_match = True
                    break
            if any_match:
                claim["reject_reason"] = "slot_could_be_matched"
                rejected.append(claim)
            else:
                verified.append(claim)
        else:
            # Unknown type — reject
            claim["reject_reason"] = f"unknown_claim_type: {ctype}"
            rejected.append(claim)

    return verified, rejected


def _aggregate_groups(verified_claims: list[dict], courses: list[dict], course_map: dict, equivalencies: dict, interp_by_group: dict | None = None) -> list[dict]:
    """
    Aggregate verified claims into groups with status/percent computed deterministically.

    Each verified claim maps a student course to a requirement group. A claim may appear
    valid for multiple groups (e.g., BIOL 3240 is both Area A and a specialization elective).
    To prevent double-counting, we assign each student course to at most ONE group:
      - Specific/satisfies_or_slot claims: course is "consumed" by that group
      - Bucket/area/lab claims: may appear in multiple groups (they accumulate credits)
    """
    # Build student course lookup
    student_courses = {}
    for c in courses:
        raw = c.get("id", c.get("code", ""))
        resolved, _ = _resolve_code(raw, course_map, equivalencies)
        student_courses[raw] = c
        student_courses[resolved] = c

    # Collect unique group names from claims
    group_names: set[str] = set()
    for cl in verified_claims:
        gn = cl.get("group_name", "")
        if gn:
            group_names.add(gn)

    # Determine group type from claim types present
    def _group_type(claims: list[dict]) -> str:
        has_bucket = any(c.get("type") == "satisfies_bucket" for c in claims)
        has_area = any(c.get("type") == "satisfies_area" for c in claims)
        has_lab = any(c.get("type") == "satisfies_lab" for c in claims)
        if has_bucket or has_area or has_lab:
            return "accumulating"  # credits/buckets can accumulate across multiple groups
        return "consuming"         # specific/or_slot: course is consumed when matched

    groups = []
    # Track which courses have already been "consumed" by a consuming group
    consumed: set[str] = set()

    for gn in sorted(group_names):
        group_claims = [c for c in verified_claims if c.get("group_name") == gn]
        gtype = _group_type(group_claims)

        bucket_credits = 0
        satisfied_details = []
        remaining_slots = []
        satisfied_courses: set[str] = set()  # for dedup within group

        for cl in group_claims:
            sc = cl.get("student_course", "")
            credits = cl.get("credits", 0)
            ctype_ = cl.get("type", "")

            if ctype_ in ("satisfies_bucket", "satisfies_area", "satisfies_lab", "satisfies_specific", "satisfies_or_slot"):
                # Deduplicate — same course may be claimed multiple times across calls
                if sc in satisfied_courses:
                    continue

                # For consuming groups (specific/or_slot), skip if this course was already
                # used to satisfy a different consuming group (prevents double-counting).
                # Accumulating groups (bucket/area/lab) are explicitly allowed to appear
                # in multiple groups — only mark consumed for consuming groups.
                if gtype == "consuming":
                    if sc in consumed:
                        continue
                    consumed.add(sc)

                # Get display info
                tc = student_courses.get(sc) or student_courses.get(sc)
                title = tc.get("title", cl.get("explanation", "")) if tc else cl.get("explanation", "")
                resolved_sc, was_legacy = _resolve_code(sc, course_map, equivalencies)
                note = ""
                if was_legacy:
                    for raw_code, c_data in student_courses.items():
                        if c_data == tc:
                            note = f"via {raw_code}"
                            break
                satisfied_details.append({
                    "code": resolved_sc,
                    "title": title,
                    "note": note,
                    "credits": credits,
                })
                satisfied_courses.add(sc)
                if ctype_ in ("satisfies_bucket", "satisfies_area", "satisfies_lab"):
                    bucket_credits += credits
            elif ctype_ == "unmatched_slot":
                remaining_slots.append(cl.get("slot_description", ""))

        # Compute status and percent deterministically
        has_bucket = any(c.get("type") == "satisfies_bucket" for c in group_claims)
        has_area = any(c.get("type") == "satisfies_area" for c in group_claims)
        has_lab = any(c.get("type") == "satisfies_lab" for c in group_claims)
        has_specific = any(c.get("type") == "satisfies_specific" for c in group_claims)
        has_or_slot = any(c.get("type") == "satisfies_or_slot" for c in group_claims)

        # Initialize before the if/elif chain so all branches can access it
        remaining_credits = 0

        if has_bucket:
            # Credit bucket — use target_credits from group_interpretations if available
            interp = (interp_by_group or {}).get(gn, {})
            target = int(interp.get("target_credits") or 0)
            if target > 0:
                percent = min(100, int(bucket_credits / target * 100))
                if bucket_credits >= target:
                    status = "SATISFIED"
                elif bucket_credits > 0:
                    status = "PARTIAL"
                else:
                    status = "MISSING"
                credit_progress = f"{bucket_credits}/{target}"
            else:
                # No target known — fall back to remaining-slot estimate
                for slot in remaining_slots:
                    opts = re.findall(r'([A-Z]{2,}\s*\d+\w*)', slot)
                    if not opts:
                        remaining_credits += 3
                if bucket_credits > 0 and not remaining_slots:
                    status = "SATISFIED"
                    percent = 100
                elif bucket_credits > 0:
                    status = "PARTIAL"
                    percent = min(100, int(bucket_credits / (bucket_credits + remaining_credits) * 100)) if remaining_credits > 0 else 100
                else:
                    status = "MISSING"
                    percent = 0
                credit_progress = f"{bucket_credits}/?"
        elif has_area or has_lab:
            if not remaining_slots:
                status = "SATISFIED"
                percent = 100
            else:
                status = "PARTIAL"
                percent = int(len(satisfied_courses) / (len(satisfied_courses) + len(remaining_slots)) * 100) if remaining_slots else 100
            credit_progress = ""
        elif has_specific or has_or_slot:
            if not remaining_slots:
                status = "SATISFIED"
                percent = 100
            else:
                status = "PARTIAL"
                total = len(satisfied_courses) + len(remaining_slots)
                percent = int(len(satisfied_courses) / total * 100) if total > 0 else 0
            credit_progress = f"{len(satisfied_courses)}/{len(satisfied_courses)+len(remaining_slots)}" if remaining_slots else ""
        else:
            status = "PARTIAL"
            percent = int(len(satisfied_courses) / max(1, len(satisfied_courses) + len(remaining_slots)) * 100)
            credit_progress = ""

        groups.append({
            "name": gn,
            "status": status,
            "percent": percent,
            "satisfied": [d["code"] for d in satisfied_details],
            "satisfied_details": satisfied_details,
            "remaining": remaining_slots,
            "remaining_details": [],
            "credit_progress": credit_progress,
        })

    return groups


def _recover_json(raw: str) -> dict[str, Any] | None:
    """Attempt to recover a truncated JSON response.

    Tries three strategies in order:
    1. Strip markdown code fences and parse directly
    2. Find the last complete JSON object (balanced braces)
    3. Extract everything between the outermost { }
    """
    raw = raw.strip()
    # Strip markdown fences
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    # Remove thinking tags
    raw = re.sub(r"<think(?:ing)?>[\s\S]*?</think(?:ing)?>", "", raw, flags=re.IGNORECASE).strip()

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: find last balanced closing brace
    # Walk backwards from end to find where the top-level object closes
    depth = 0
    in_string = False
    escape_next = False
    last_valid = -1
    for i, ch in enumerate(raw):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                last_valid = i + 1

    if last_valid > 0:
        fragment = raw[:last_valid]
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            pass

    # Strategy 3: extract outermost { }
    outer_match = re.search(r'\{[\s\S]*\}', raw)
    if outer_match:
        try:
            return json.loads(outer_match.group())
        except json.JSONDecodeError:
            pass

    return None


async def _llm_audit_program(prog_name: str, prog: dict, courses: list[dict], requirements_text: str | None = None) -> dict:
    """Audit one program using LLM Claims → Deterministic Verification pipeline."""
    school = prog.get("school", "")

    # Step 1: Get requirements via chat pipeline (skip if caller already has the text)
    if requirements_text is None:
        query = f"What are the complete degree requirements for the {prog_name}? List every required course, credit bucket, area requirement, and specialization requirement with course codes."
        print(f"[llm-audit] step1: retrieving requirements for {prog_name!r}")
        result = await asyncio.to_thread(agentic_retrieve, query)
        requirements_text = result.answer
    print(f"[llm-audit] step1 done: {len(requirements_text)} chars")

    if not requirements_text or len(requirements_text) < 50:
        return {
            "program": prog_name, "school": school, "overall_percent": 0, "groups": [],
            "notes": ["Could not retrieve requirements from bulletin"], "audit_mode": "failed",
        }

    courses_text = _format_courses_text(courses)
    course_map = _load_course_map()
    equivalencies = _load_equivalencies()

    # Step 2: LLM generates structured claims
    prompt = _CLAIMS_PROMPT.format(
        equivalency_context=_EQUIVALENCY_CONTEXT,
        prog_name=prog_name,
        requirements_text=requirements_text,
        courses_text=courses_text,
    )
    print(f"[llm-audit] step2: claims LLM call ({len(prompt)} chars)")
    raw = await asyncio.to_thread(complete, _LLM_MODEL, prompt)
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()

    claims_data = _recover_json(raw)
    if claims_data is None:
        print(f"[llm-audit] claims JSON parse failed, raw ({len(raw)} chars): {raw[:300]}")
        # For college audits (no program type), don't try get_requirements fallback
        is_college_audit = not prog.get("type")
        if not is_college_audit:
            try:
                requirements = await asyncio.to_thread(get_requirements, prog_name, prog.get("type"), school)
                return _deterministic_audit(prog_name, requirements, courses)
            except Exception:
                pass
        return {
            "program": prog_name, "school": school, "overall_percent": 0, "groups": [],
            "notes": ["LLM claims parse failed"], "audit_mode": "failed",
        }

    claims = claims_data.get("claims", [])
    group_interps = claims_data.get("group_interpretations", [])
    print(f"[llm-audit] step2: {len(claims)} claims generated")

    # Attach group interpretations to claims for verification
    interp_by_group = {ig.get("group_name", ""): ig for ig in group_interps}
    for cl in claims:
        gn = cl.get("group_name", "")
        if gn in interp_by_group:
            cl["bucket_interpretation"] = interp_by_group[gn]

    # Step 3: Deterministic verification
    print(f"[llm-audit] step3: verifying {len(claims)} claims")
    verified, rejected = _verify_claims(claims, courses, course_map, equivalencies)
    print(f"[llm-audit] step3: {len(verified)} verified, {len(rejected)} rejected")
    for r in rejected[:5]:
        print(f"  REJECTED: {r.get('student_course', r.get('slot_description', '?'))} — {r.get('reject_reason', '')}")

    # Step 4: Aggregate into groups
    groups = _aggregate_groups(verified, courses, course_map, equivalencies, interp_by_group)

    # Compute overall
    overall = int(sum(g["percent"] for g in groups) / len(groups)) if groups else 0
    print(f"[llm-audit] done: {len(groups)} groups, {overall}% overall")

    return {
        "program": prog_name,
        "school": school,
        "overall_percent": overall,
        "groups": groups,
        "audit_mode": "claims_verified",
    }


async def _audit_one_program(programs: list[dict], courses: list[dict], prog_name: str) -> dict:
    """Audit one program using LLM-based pipeline with deterministic fallback."""
    prog = next((p for p in programs if p.get("name") == prog_name), {"name": prog_name})

    try:
        return await _llm_audit_program(prog_name, prog, courses)
    except Exception as e:
        print(f"[audit] LLM audit failed for {prog_name!r}: {e}, falling back to deterministic")
        try:
            requirements = await asyncio.to_thread(
                get_requirements, prog_name, prog.get("type"), prog.get("school")
            )
            return _deterministic_audit(prog_name, requirements, courses)
        except Exception as e2:
            print(f"[audit] deterministic fallback also failed: {e2}")
            return {
                "program": prog_name,
                "school": prog.get("school", ""),
                "overall_percent": 0,
                "groups": [],
                "notes": [f"Could not audit: {e}"],
                "audit_mode": "failed",
            }


async def _compute_college_audit(programs: list[dict], courses: list[dict]) -> dict | None:
    if not programs:
        return None
    first = programs[0] if isinstance(programs[0], dict) else {}
    school = first.get("school", "arts-sciences")
    try:
        college_req = await asyncio.to_thread(get_college_requirements, school)
        prog_name = college_req.get("program", f"{school.title()} Graduation Requirements")
        school_display = college_req.get("school", school)
        requirements_text = college_req.get("requirements_text", "")

        if not requirements_text:
            return {
                "program": prog_name, "school": school_display,
                "overall_percent": 0, "groups": [], "is_college": True,
                "error": "Could not retrieve college requirements",
            }

        # Use dedicated college audit prompt (simpler than claims pipeline — distribution
        # requirements don't need OR-logic or specific-code verification)
        prompt = _COLLEGE_AUDIT_PROMPT.format(
            equivalency_context=_EQUIVALENCY_CONTEXT,
            core_skills_context=_build_core_skills_context(courses),
            prog_name=prog_name,
            school=school_display,
            requirements_text=requirements_text,
            courses_text=_format_courses_text(courses),
        )
        print(f"[college-audit] LLM call ({len(prompt)} chars)")
        raw = await asyncio.to_thread(complete, _LLM_MODEL, prompt)
        parsed = _recover_json(raw or "")
        if parsed is None:
            print(f"[college-audit] JSON parse failed, raw: {(raw or '')[:200]}")
            return {
                "program": prog_name, "school": school_display,
                "overall_percent": 0, "groups": [], "is_college": True,
                "error": "LLM audit parse failed",
            }

        groups = parsed.get("groups", [])
        for g in groups:
            g.setdefault("name", "Unknown")
            g.setdefault("status", "MISSING")
            g.setdefault("percent", 0)
            g.setdefault("satisfied", [])
            g.setdefault("remaining", [])
            g.setdefault("credit_progress", "")
            # Fix: override status/percent based on credit_progress arithmetic
            cp = g.get("credit_progress", "")
            if cp and "/" in cp:
                try:
                    earned_str, target_str = cp.split("/", 1)
                    earned = float(re.sub(r"[^\d.]", "", earned_str) or "0")
                    target = float(re.sub(r"[^\d.]", "", target_str) or "0")
                    if target > 0:
                        if earned >= target:
                            g["status"] = "SATISFIED"
                            g["percent"] = 100
                            g["remaining"] = []
                        else:
                            # LLM said SATISFIED but credits don't add up — correct it
                            computed_pct = int(earned / target * 100)
                            g["percent"] = computed_pct
                            if g.get("status") == "SATISFIED":
                                g["status"] = "PARTIAL" if earned > 0 else "MISSING"
                except (ValueError, ZeroDivisionError):
                    pass

        overall = parsed.get("overall_percent", 0)
        if groups:
            overall = int(sum(g["percent"] for g in groups) / len(groups))

        print(f"[college-audit] done: {len(groups)} groups, {overall}%")
        return {
            "program": prog_name,
            "school": school_display,
            "overall_percent": overall,
            "groups": groups,
            "is_college": True,
        }
    except Exception as e:
        print(f"[college-audit] failed: {e}")
        return {
            "program": f"{school.title()} Graduation Requirements",
            "school": school,
            "overall_percent": 0,
            "groups": [],
            "is_college": True,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/audit-full")
@limiter.limit("3/minute")
async def audit_full(req: AuditFullRequest, request: Request):
    """Full audit — returns all program + college results."""
    courses = req.courses or []
    programs = req.programs or ([{"name": req.program}] if req.program else [])

    if not courses:
        raise HTTPException(400, "No courses provided in request body.")
    if not programs:
        raise HTTPException(400, "No programs provided in request body.")

    valid_names = [p.get("name", "") for p in programs if p.get("name")]
    audit_results = [await _audit_one_program(programs, courses, n) for n in valid_names]
    college_audit = await _compute_college_audit(programs, courses)

    return {
        "student": req.student or {},
        "gpa": req.gpa or 0.0,
        "audits": audit_results,
        "college_audit": college_audit,
    }


@router.post("/audit-full/stream")
@limiter.limit("3/minute")
async def audit_full_stream(req: AuditFullRequest, request: Request):
    """Streaming audit — emits SSE events as each program completes."""
    courses = req.courses or []
    programs = req.programs or ([{"name": req.program}] if req.program else [])

    if not courses:
        async def _err():
            yield _sse_audit("error", {"message": "No courses provided in request body."})
            yield _sse_audit("done", {"ok": False})
        return StreamingResponse(_err(), media_type="text/event-stream")

    valid_names = [p.get("name", "") for p in programs if p.get("name")]

    async def event_stream():
        yield _sse_audit("status", {
            "phase": "programs",
            "message": f"Auditing {len(valid_names)} program(s)…",
            "pending": valid_names,
        })

        # Run programs sequentially — each audit makes 2 LLM calls; running them
        # concurrently floods the API and causes timeouts on slower programs.
        audit_results: list[dict] = []
        for i, name in enumerate(valid_names):
            result = await _audit_one_program(programs, courses, name)
            audit_results.append(result)
            yield _sse_audit("program_complete", {
                "program": name,
                "overall_percent": result.get("overall_percent", 0),
                "result": result,
                "completed_count": i + 1,
                "total_programs": len(valid_names),
            })

        yield _sse_audit("status", {"phase": "college", "message": "Computing college requirements…"})
        college_audit = await _compute_college_audit(programs, courses)
        if college_audit:
            yield _sse_audit("college_complete", {
                "program": college_audit.get("program", ""),
                "overall_percent": college_audit.get("overall_percent", 0),
                "result": college_audit,
            })

        yield _sse_audit("result", {
            "student": req.student or {},
            "gpa": req.gpa or 0.0,
            "audits": audit_results,
            "college_audit": college_audit,
        })
        yield _sse_audit("done", {"ok": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
