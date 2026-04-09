"""
Audit Engine — legacy simple audit (deprecated).

The production audit path is /api/audit-full (routers/audit_full.py).
The hardcoded PROGRAMS dict has been removed; all program requirements
are now retrieved dynamically from the bulletin via the RAG pipeline.
"""
from .equivalency_resolver import resolve


def _resolve_course(course_code: str) -> tuple[str | None, bool, str]:
    r = resolve(course_code)
    if r.get("equivalent"):
        return r["official"], True, f"{r['official']} (via {course_code})"
    elif r.get("not_equivalent"):
        return None, False, f"{course_code} NOT equivalent — {r.get('note', '')}"
    return None, None, f"{course_code} (not found in equivalency table)"


def audit(student_courses: list[str], program_code: str, minor_code: str | None = None) -> dict:
    """
    Deprecated. Use POST /api/audit-full instead.
    """
    raise ValueError(
        f"The simple /api/audit endpoint is deprecated. "
        f"Use POST /api/audit-full with your transcript profile."
    )
