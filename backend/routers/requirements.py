"""
GET /api/requirements — legacy endpoint.
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["requirements"])


@router.get("/requirements")
async def get_requirements(program: str):
    """
    Legacy requirements endpoint.

    The old hardcoded requirements table was removed.
    Use POST /api/audit-full to retrieve dynamic requirement status.
    """
    raise HTTPException(
        status_code=410,
        detail=(
            "The /api/requirements endpoint is deprecated. "
            "Use POST /api/audit-full for dynamic program requirements."
        ),
    )
