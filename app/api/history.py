"""
ResuMax — History API Routes
Paginated analysis history for the current user.
"""

import structlog
from fastapi import APIRouter, Depends, Query
from app.api.deps import get_current_user
from app.services.supabase import get_user_analyses

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history")
async def get_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=50, description="Items per page"),
    user: dict = Depends(get_current_user),
):
    """
    Get paginated analysis history for the current user.
    Returns lite versions (no full results, just scores and status).
    """
    result = await get_user_analyses(
        user_id=user["id"],
        page=page,
        limit=limit,
    )

    logger.info(
        "history_fetched",
        user_id=user["id"],
        page=page,
        total=result.get("total", 0),
    )

    return result
