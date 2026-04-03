"""
ResuMax Backend — Supabase Service
Provides a singleton Supabase client using the service_role key
which bypasses Row Level Security for backend operations.
"""

import structlog
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from app.config import get_settings

logger = structlog.get_logger(__name__)

# ── Singleton Client ─────────────────────────────────────────────
_supabase_client: Client | None = None


def get_supabase_client() -> Client:
    """
    Get or create the Supabase client singleton.
    Uses service_role key which bypasses RLS — safe for backend-only operations.
    """
    global _supabase_client

    if _supabase_client is None:
        settings = get_settings()
        _supabase_client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_service_role_key,
            options=ClientOptions(
                auto_refresh_token=False,
                persist_session=False,
            ),
        )
        logger.info(
            "supabase_client_initialized",
            url=settings.supabase_url[:40] + "...",
        )

    return _supabase_client


# ── Auth Helpers ─────────────────────────────────────────────────

async def verify_user_token(token: str) -> dict | None:
    """
    Verify a Supabase JWT token and return the user object.
    Returns None if the token is invalid or expired.
    """
    try:
        client = get_supabase_client()
        user_response = client.auth.get_user(token)
        if user_response and user_response.user:
            logger.info("token_verified", user_id=str(user_response.user.id))
            return {
                "id": str(user_response.user.id),
                "email": user_response.user.email,
                "full_name": user_response.user.user_metadata.get("full_name", ""),
            }
        return None
    except Exception as e:
        logger.warning("token_verification_failed", error=str(e))
        return None


# ── Database Helpers ─────────────────────────────────────────────

async def create_profile(user_id: str, email: str, full_name: str = "") -> dict:
    """Create a user profile in the profiles table."""
    client = get_supabase_client()
    result = client.table("profiles").insert({
        "id": user_id,
        "email": email,
        "full_name": full_name,
    }).execute()
    logger.info("profile_created", user_id=user_id)
    return result.data[0] if result.data else {}


async def get_profile(user_id: str) -> dict | None:
    """Get a user profile by ID."""
    client = get_supabase_client()
    result = client.table("profiles").select("*").eq("id", user_id).execute()
    return result.data[0] if result.data else None


# ── Analysis Helpers ─────────────────────────────────────────────

async def create_analysis(user_id: str, resume_file_path: str, resume_text: str,
                          job_description: str, job_title: str = "") -> dict:
    """Create a new analysis record with 'pending' status."""
    client = get_supabase_client()
    result = client.table("analyses").insert({
        "user_id": user_id,
        "resume_file_path": resume_file_path,
        "resume_text": resume_text,
        "job_description": job_description,
        "job_title": job_title,
        "status": "pending",
        "current_step": 0,
    }).execute()
    logger.info("analysis_created", user_id=user_id, analysis_id=result.data[0]["id"])
    return result.data[0]


async def update_analysis_status(analysis_id: str, status: str, step: int,
                                  **extra_fields) -> dict:
    """Update the pipeline status and any result fields for an analysis."""
    client = get_supabase_client()
    update_data = {
        "status": status,
        "current_step": step,
        **extra_fields,
    }
    result = client.table("analyses").update(update_data).eq("id", analysis_id).execute()
    logger.info("analysis_status_updated", analysis_id=analysis_id, status=status, step=step)
    return result.data[0] if result.data else {}


async def get_analysis(analysis_id: str) -> dict | None:
    """Get a single analysis by ID."""
    client = get_supabase_client()
    result = client.table("analyses").select("*").eq("id", analysis_id).execute()
    return result.data[0] if result.data else None


async def get_user_analyses(user_id: str, page: int = 1, limit: int = 10) -> dict:
    """Get paginated analysis history for a user."""
    client = get_supabase_client()
    offset = (page - 1) * limit

    # Get total count
    count_result = client.table("analyses") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .execute()

    # Get paginated results
    result = client.table("analyses") \
        .select("id, job_title, ats_score, status, created_at") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .range(offset, offset + limit - 1) \
        .execute()

    return {
        "analyses": result.data,
        "total": count_result.count or 0,
        "page": page,
        "limit": limit,
    }

async def delete_analysis(analysis_id: str):
    """Delete an analysis from the database."""
    client = get_supabase_client()
    # Supabase cascade delete will remove associated storage files if set up, 
    # but for now we just delete the DB record.
    client.table("analyses").delete().eq("id", analysis_id).execute()


# ── Storage Helpers ──────────────────────────────────────────────

async def upload_resume(user_id: str, analysis_id: str,
                        file_bytes: bytes, file_name: str) -> str:
    """
    Upload a resume file to Supabase Storage.
    Returns the storage path.
    """
    client = get_supabase_client()
    storage_path = f"{user_id}/{analysis_id}/{file_name}"

    # Determine content type
    content_type = "application/pdf"
    if file_name.endswith(".docx"):
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif file_name.endswith(".txt"):
        content_type = "text/plain"

    client.storage.from_("resumax-resumes").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": content_type},
    )
    logger.info("resume_uploaded", path=storage_path)
    return storage_path


async def download_resume(storage_path: str) -> bytes:
    """Download a resume file from Supabase Storage."""
    client = get_supabase_client()
    data = client.storage.from_("resumax-resumes").download(storage_path)
    return data


# ── Realtime Helpers ─────────────────────────────────────────────

async def broadcast_progress(analysis_id: str, step: int, status: str,
                              message: str, percentage: int) -> None:
    """
    Broadcast pipeline progress to the frontend via Supabase Realtime.
    The frontend subscribes to channel `analysis:{analysis_id}`.
    """
    try:
        client = get_supabase_client()
        channel = client.channel(f"analysis:{analysis_id}")
        channel.subscribe()
        channel.send_broadcast(
            event="progress",
            data={
                "step": step,
                "status": status,
                "message": message,
                "percentage": percentage,
            },
        )
        logger.info(
            "progress_broadcast",
            analysis_id=analysis_id,
            step=step,
            message=message,
        )
    except Exception as e:
        logger.error("broadcast_failed", analysis_id=analysis_id, error=str(e))
