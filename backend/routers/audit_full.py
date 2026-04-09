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

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

_BACKEND_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from services.requirements_extractor import get_requirements, get_college_requirements
from services.equivalency_resolver import resolve
from pageindex_agent.utils import ChatGPT_API

router = APIRouter(prefix="/api", tags=["audit"])
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")


class AuditFullRequest(BaseModel):
    program: str | None = None          # legacy singular
    programs: list[dict] | None = None  # [{name: "...", type: "...", school: "..."}]
    courses: list[dict] | None = None   # [{id: "BIOL 296", title: "...", credits: 3, grade: "A"}]
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
    base = _normalize_code(code)
    variants = {base}
    resolved, equiv, _ = _resolve_course(base)
    if equiv is True and resolved:
        variants.add(_normalize_code(resolved))
    m = re.match(r"^([A-Z&]+)\s+(\d{3,4}[A-Z]?)$", base)
    if not m:
        return variants
    dept, num = m.group(1), m.group(2)
    digits_only = num[:-1] if num and num[-1].isalpha() else num
    if digits_only.isdigit():
        if len(digits_only) == 3:
            variants.add(f"{dept} {digits_only}0")
        elif len(digits_only) == 4 and digits_only.endswith("0"):
            variants.add(f"{dept} {digits_only[:-1]}")
    return variants


def _audit_group(student_courses: list[dict], group: dict) -> dict:
    """Deterministic course-code matching for one requirement group."""
    required_codes = group.get("courses", [])
    required_credits = group.get("required_credits", 0)

    student_meta: dict[str, dict] = {}
    for c in student_courses:
        code = c.get("id", "")
        student_meta[code] = {
            "resolved": _resolve_course(code),
            "variants": _code_variants(code),
        }

    satisfied: list[str] = []
    satisfied_credits = 0
    satisfied_set: set[str] = set()

    for req in required_codes:
        req_variants = _code_variants(_normalize_code(req))
        for sc in student_courses:
            sc_code = sc.get("id", "")
            if sc_code in satisfied_set:
                continue
            meta = student_meta.get(sc_code, {"resolved": (None, None, ""), "variants": set()})
            resolved, equiv, note = meta["resolved"]
            sc_variants: set[str] = meta["variants"]
            if equiv is True and resolved and _normalize_code(resolved) in req_variants:
                satisfied.append(note)
                satisfied_set.add(sc_code)
                satisfied_credits += sc.get("credits", 3)
                break
            elif sc_variants.intersection(req_variants):
                satisfied.append(sc_code)
                satisfied_set.add(sc_code)
                satisfied_credits += sc.get("credits", 3)
                break

    remaining = [req for req in required_codes if not any(req in s for s in satisfied)]
    num_required = len(required_codes)
    num_satisfied = len(satisfied)
    percent = int((num_satisfied / num_required) * 100) if num_required else 100

    if num_satisfied == num_required:
        status = "SATISFIED"
    elif num_satisfied > 0:
        status = "PARTIAL"
    else:
        status = "MISSING"

    return {
        "name": group.get("name", ""),
        "status": status,
        "percent": percent,
        "satisfied": satisfied,
        "remaining": remaining,
        "credit_progress": f"{satisfied_credits}/{required_credits}",
    }


# ---------------------------------------------------------------------------
# Step B: focused LLM course comparison
# ---------------------------------------------------------------------------

def _llm_audit_courses(program: dict, student_courses: list[dict], requirements: dict) -> dict:
    """
    Step B of the audit pipeline.

    Receives pre-parsed requirement groups (from Step A / get_requirements cache).
    Sends a small, focused prompt asking the LLM to match student courses against
    each group and return structured JSON.  No raw bulletin text involved here.
    """
    program_name = program.get("name", "")
    program_type = program.get("type", "")
    school = requirements.get("school", program.get("school", ""))

    compact_courses = [
        {
            "id": c.get("id", ""),
            "credits": c.get("credits", 0),
            "grade": c.get("grade", ""),
            "variants": sorted(list(_code_variants(c.get("id", ""))))[:4],
        }
        for c in student_courses[:180]
    ]

    req_groups = requirements.get("groups", [])

    prompt = (
        "You are a WashU degree audit assistant.\n"
        f"Program: {program_name} ({program_type})\n"
        f"School: {school}\n\n"
        "Requirement groups from the bulletin:\n"
        f"{json.dumps(req_groups, ensure_ascii=True)}\n\n"
        "Student courses with old/new code variants:\n"
        f"{json.dumps(compact_courses, ensure_ascii=True)}\n\n"
        "For each requirement group:\n"
        "- Match student courses by 'id' or any 'variant' against the group's required course codes.\n"
        "- percent = (matched / total required) * 100, capped at 100.\n"
        "- credit_progress = 'X/Y' (credits earned toward group / required_credits).\n"
        "- status: SATISFIED=100%, PARTIAL=1-99%, MISSING=0%.\n\n"
        "Return ONLY valid JSON:\n"
        '{"overall_percent":0,"groups":['
        '{"name":"","status":"SATISFIED|PARTIAL|MISSING","percent":0,'
        '"satisfied":["course_id"],"remaining":["requirement_code"],"credit_progress":"x/y"}'
        "]}"
    )

    raw = ChatGPT_API(MINIMAX_MODEL, prompt, stream=False) or ""
    raw = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<thinking[\s\S]*?</thinking>", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("```json", "").replace("```", "")

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"LLM audit returned no JSON: {raw[:200]!r}")

    parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM audit returned non-dict JSON")

    groups = parsed.get("groups", []) or []
    overall = int(parsed.get("overall_percent", 0) or 0)
    if groups and overall == 0:
        pcts = [int(g.get("percent", 0) or 0) for g in groups if isinstance(g, dict)]
        if pcts:
            overall = int(sum(pcts) / len(pcts))

    return {
        "program": program_name,
        "extracted_program": requirements.get("program", program_name),
        "school": school,
        "overall_percent": overall,
        "groups": groups,
        "notes": [],
        "audit_mode": "two_step",
    }


def _deterministic_audit(program_name: str, requirements: dict, student_courses: list[dict]) -> dict:
    """Fallback: pure code-matching, no LLM comparison call."""
    groups_results: list[dict] = []
    total_pct = 0
    for group in requirements.get("groups", []):
        result = _audit_group(student_courses, group)
        groups_results.append(result)
        total_pct += result["percent"]
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


# ---------------------------------------------------------------------------
# Per-program audit: 2-step pipeline
# ---------------------------------------------------------------------------

async def _audit_one_program(programs: list[dict], courses: list[dict], prog_name: str) -> dict:
    prog = next((p for p in programs if p.get("name") == prog_name), {"name": prog_name})

    # Step A (LLM, cached): parse structured requirement groups from bulletin
    try:
        requirements = await asyncio.to_thread(
            get_requirements, prog_name, prog.get("type"), prog.get("school")
        )
    except Exception as e:
        return {
            "program": prog_name,
            "school": prog.get("school", ""),
            "overall_percent": 0,
            "groups": [],
            "notes": [f"Could not retrieve requirements from bulletin: {e}"],
            "audit_mode": "failed",
        }

    # Step B (LLM): match student courses against parsed requirements
    try:
        return await asyncio.to_thread(_llm_audit_courses, prog, courses, requirements)
    except Exception as e:
        print(f"[audit] LLM comparison failed for {prog_name!r}: {e} — using deterministic fallback")
        return _deterministic_audit(prog_name, requirements, courses)


async def _compute_college_audit(programs: list[dict], courses: list[dict]) -> dict | None:
    if not programs:
        return None
    first = programs[0] if isinstance(programs[0], dict) else {}
    school = first.get("school", "arts-sciences")
    try:
        college_req = await asyncio.to_thread(get_college_requirements, school)
        college_groups: list[dict] = []
        total_pct = 0
        for group in college_req.get("groups", []):
            result = _audit_group(courses, group)
            college_groups.append(result)
            total_pct += result["percent"]
        n = len(college_groups)
        return {
            "program": college_req.get("program", f"{school.title()} Graduation Requirements"),
            "school": college_req.get("school", school),
            "overall_percent": int(total_pct / n) if n else 0,
            "groups": college_groups,
            "is_college": True,
        }
    except Exception as e:
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
async def audit_full(req: AuditFullRequest, request: Request):
    """Full audit — returns all program + college results."""
    current_profile = getattr(request.app.state, "current_profile", None)

    if req.courses is not None or req.program is not None:
        courses = req.courses or []
        programs = req.programs or ([{"name": req.program}] if req.program else [])
    else:
        if current_profile is None:
            raise HTTPException(
                400,
                "No profile uploaded yet. POST a transcript to /api/upload-transcript first, "
                "or provide {program, courses} in the request body.",
            )
        courses = _extract_course_codes(current_profile)
        programs = current_profile.get("programs", [])

    if not courses:
        raise HTTPException(400, "No courses found in profile or request body.")

    valid_names = [p.get("name", "") for p in programs if p.get("name")]
    audit_results = [await _audit_one_program(programs, courses, n) for n in valid_names]
    college_audit = await _compute_college_audit(programs, courses)

    return {
        "student": (current_profile or {}).get("student", {}),
        "gpa": (current_profile or {}).get("cumulative", {}).get("gpa")
        or (current_profile or {}).get("gpa", 0.0),
        "audits": audit_results,
        "college_audit": college_audit,
    }


@router.post("/audit-full/stream")
async def audit_full_stream(req: AuditFullRequest, request: Request):
    """Streaming audit — emits SSE events as each program completes."""
    current_profile = getattr(request.app.state, "current_profile", None)

    if req.courses is not None or req.program is not None:
        courses = req.courses or []
        programs = req.programs or ([{"name": req.program}] if req.program else [])
    else:
        if current_profile is None:
            async def _err():
                yield _sse_audit("error", {"message": "No profile uploaded yet."})
                yield _sse_audit("done", {"ok": False})
            return StreamingResponse(_err(), media_type="text/event-stream")
        courses = _extract_course_codes(current_profile)
        programs = current_profile.get("programs", [])

    if not courses:
        async def _err2():
            yield _sse_audit("error", {"message": "No courses found in profile or request body."})
            yield _sse_audit("done", {"ok": False})
        return StreamingResponse(_err2(), media_type="text/event-stream")

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
            "student": (current_profile or {}).get("student", {}),
            "gpa": (current_profile or {}).get("cumulative", {}).get("gpa")
            or (current_profile or {}).get("gpa", 0.0),
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
