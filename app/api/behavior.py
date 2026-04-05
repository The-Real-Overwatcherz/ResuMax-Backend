"""
ResuMax Backend — Behavior Profile API
Exposes user behavioral profiles for frontend display and management.
"""

import structlog
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.services.behavior_profiler import (
    load_profile_from_db,
    save_profile_to_db,
    _default_profile,
    _profile_cache,
    BEHAVIOR_DIMENSIONS,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/behavior", tags=["behavior"])


@router.get("/profile")
async def get_behavior_profile(user: dict = Depends(get_current_user)):
    """
    Get the current user's behavioral profile.
    Returns cached in-memory profile, falls back to DB, then defaults.
    """
    user_id = user["id"]

    # Check in-memory cache first
    cached = _profile_cache.get(user_id)
    if cached:
        return {"profile": cached["profile"], "source": "live"}

    # Try database
    db_profile = await load_profile_from_db(user_id)
    if db_profile:
        return {"profile": db_profile, "source": "saved"}

    # Return defaults
    return {"profile": _default_profile(), "source": "default"}


@router.get("/dimensions")
async def get_behavior_dimensions():
    """
    Return all behavior dimensions and their possible values.
    Useful for the frontend to render profile visualizations.
    """
    dimensions = {}
    for dim_name, options in BEHAVIOR_DIMENSIONS.items():
        dimensions[dim_name] = {
            "options": list(options.keys()),
            "descriptions": options,
        }
    return {"dimensions": dimensions}


@router.delete("/profile")
async def reset_behavior_profile(user: dict = Depends(get_current_user)):
    """Reset a user's behavioral profile (clear cache and DB)."""
    user_id = user["id"]

    # Clear cache
    if user_id in _profile_cache:
        del _profile_cache[user_id]

    # Reset DB to defaults
    await save_profile_to_db(user_id, _default_profile())

    logger.info("behavior_profile_reset", user_id=user_id)
    return {"message": "Behavior profile reset to defaults", "profile": _default_profile()}
