"""
Feedback router — course code submission endpoint.
Allows students to suggest missing legacy→current course code mappings.
Submissions go to pending_submissions and are NOT auto-applied (human review required).
"""
import json
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.responses import JSONResponse

_DATA_DIR = Path(os.getenv("DATA_DIR", "../data"))
_CODE_MAP_PATH = _DATA_DIR / "course_code_map.json"

router = APIRouter(prefix="/api", tags=["feedback"])

_CODE_PATTERN = re.compile(r"^[A-Z&][A-Z0-9&\-\s]*(?:\s|\t)\d+[A-Z]?(?:\s|\t)?[A-Z0-9]*$", re.IGNORECASE)


class CourseCodeFeedback(BaseModel):
    old_code: str
    proposed_new_code: str
    notes: str | None = None


def _code_valid(code: str) -> bool:
    stripped = code.strip()
    if not stripped:
        return False
    parts = stripped.split()
    if len(parts) < 2:
        return False
    # Must have department-like prefix followed by numeric course number
    return bool(re.match(r"^[A-Z&\-]+$", parts[0])) and bool(re.search(r"\d", parts[1]))


def _load_code_map() -> dict:
    if not _CODE_MAP_PATH.exists():
        return {"_meta": {}, "mappings": {}, "pending_submissions": []}
    with open(_CODE_MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_code_map(data: dict) -> None:
    tmp = str(_CODE_MAP_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    import os
    os.replace(tmp, _CODE_MAP_PATH)


@router.post("/feedback/course-code")
def submit_course_code(body: CourseCodeFeedback) -> JSONResponse:
    """
    Submit a suggested legacy→current course code mapping.
    Entries are appended to pending_submissions and reviewed manually before
    being promoted to mappings (verified: false until reviewed).
    """
    old = body.old_code.strip()
    new = body.proposed_new_code.strip()
    notes = (body.notes or "").strip()

    if not old or not new:
        return JSONResponse({"ok": False, "error": "old_code and proposed_new_code are required."}, status_code=400)

    if not _code_valid(old) or not _code_valid(new):
        return JSONResponse({
            "ok": False,
            "error": "Invalid code format. Expected something like 'CHEM 111A' or 'CSE 131'."
        }, status_code=400)

    data = _load_code_map()
    mappings = data.get("mappings", {})
    pending = data.get("pending_submissions", [])

    # Silently dedupe against already-verified mappings
    if old in mappings or new in {m.get("new_code") for m in mappings.values()}:
        return JSONResponse({
            "ok": True,
            "message": "Thanks — that mapping is already in the system.",
        })

    # Also dedupe pending submissions
    if any(s.get("old_code", "").upper() == old.upper() for s in pending):
        return JSONResponse({
            "ok": True,
            "message": "Thanks — we already have that suggestion queued for review.",
        })

    pending.append({
        "old_code": old.upper(),
        "proposed_new_code": new.upper(),
        "notes": notes,
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    data["pending_submissions"] = pending
    _save_code_map(data)

    return JSONResponse({
        "ok": True,
        "message": "Thanks — we'll review this mapping and add it if correct.",
    })
