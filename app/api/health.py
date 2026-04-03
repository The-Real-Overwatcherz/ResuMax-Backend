"""
ResuMax Backend — Health Check Routes
"""

from fastapi import APIRouter
from app.config import get_settings
from app.services.supabase import get_supabase_client

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check():
    """Basic health check — no auth required."""
    settings = get_settings()
    return {
        "status": "ok",
        "version": settings.app_version,
        "app": settings.app_name,
    }


@router.get("/api/health/supabase")
async def supabase_health_check():
    """
    Deep health check — verifies Supabase connectivity by
    querying the profiles table (should return empty or data).
    """
    try:
        client = get_supabase_client()
        # Simple query to verify connection
        result = client.table("profiles").select("id").limit(1).execute()
        return {
            "status": "ok",
            "supabase": "connected",
            "message": "Supabase connection verified successfully",
        }
    except Exception as e:
        return {
            "status": "degraded",
            "supabase": "error",
            "message": str(e),
        }
