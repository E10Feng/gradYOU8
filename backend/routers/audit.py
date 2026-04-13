"""
POST /api/audit — evaluate a student's courses against degree requirements.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.audit_engine import audit

router = APIRouter(prefix="/api", tags=["audit"])


class AuditRequest(BaseModel):
    courses: list[str]
    program: str
    minor: str | None = None


@router.post("/audit")
async def audit_courses(req: AuditRequest):
    """
    Audit a student's course history against a degree program.

    Body:
        courses: list of course codes (e.g. ["CSE-E81 131", "BIOL 296"])
        program: program code (e.g. "biology-ba")
        minor: optional minor code (e.g. "cs-minor-engineering")
    """
    try:
        result = audit(req.courses, req.program, req.minor)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result
