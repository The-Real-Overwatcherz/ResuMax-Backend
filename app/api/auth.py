"""
ResuMax Backend — Auth API Routes
Handles token verification and user profile retrieval.
Note: Actual signup/login is handled client-side by Supabase Auth JS SDK.
The backend only verifies tokens and manages profiles.
"""

from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.services.supabase import get_profile

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/verify")
async def verify_token(user: dict = Depends(get_current_user)):
    """
    Verify the user's Supabase JWT token.
    Returns the user's ID and email if valid.
    """
    return {
        "user_id": user["id"],
        "email": user["email"],
        "full_name": user.get("full_name", ""),
    }


@router.get("/profile")
async def get_user_profile(user: dict = Depends(get_current_user)):
    """
    Get the authenticated user's profile from the profiles table.
    """
    profile = await get_profile(user["id"])
    if profile is None:
        return {
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name", ""),
            "avatar_url": None,
        }
    return profile
