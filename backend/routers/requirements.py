"""
GET /api/requirements — return program requirement structure.
"""
from fastapi import APIRouter, HTTPException

from services.audit_engine import PROGRAMS

router = APIRouter(prefix="/api", tags=["requirements"])


@router.get("/requirements")
async def get_requirements(program: str):
    """
    Return the requirement groups for a WashU program.

    Query params:
        program: program code (e.g. "biology-ba", "cs-minor-engineering")
    """
    if program not in PROGRAMS:
        raise HTTPException(
            status_code=404,
            detail=f"Program '{program}' not found. "
                   f"Available: {list(PROGRAMS.keys())}",
        )
    return PROGRAMS[program]
