"""
ResuMax Backend — Profile Reports API
Store and retrieve LinkedIn & GitHub profile analysis reports.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

from app.api.deps import get_current_user
from app.services.supabase import get_supabase_client

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


class SaveReportRequest(BaseModel):
    report_type: Literal["linkedin", "github", "x_twitter", "social_post"]
    profile_identifier: str  # LinkedIn URL or GitHub username
    profile_name: Optional[str] = None
    profile_image: Optional[str] = None
    overall_score: int
    report_data: dict


class ReportResponse(BaseModel):
    id: str
    report_type: str
    profile_identifier: str
    profile_name: Optional[str]
    profile_image: Optional[str]
    overall_score: int
    report_data: dict
    created_at: str


@router.post("/save")
async def save_report(
    request: SaveReportRequest,
    user: dict = Depends(get_current_user),
):
    """Save a LinkedIn or GitHub profile analysis report."""
    user_id = user["id"]
    
    logger.info(
        "save_report_start",
        user_id=user_id,
        report_type=request.report_type,
        profile=request.profile_identifier,
    )
    
    supabase = get_supabase_client()
    
    try:
        result = supabase.table("profile_reports").insert({
            "user_id": user_id,
            "report_type": request.report_type,
            "profile_identifier": request.profile_identifier,
            "profile_name": request.profile_name,
            "profile_image": request.profile_image,
            "overall_score": request.overall_score,
            "report_data": request.report_data,
        }).execute()
        
        report = result.data[0] if result.data else None
        
        if not report:
            raise HTTPException(status_code=500, detail="Failed to save report")
        
        logger.info("save_report_success", report_id=report["id"])
        
        return {
            "id": report["id"],
            "message": "Report saved successfully",
        }
        
    except Exception as e:
        logger.error("save_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to save report: {str(e)}")


@router.get("/")
async def list_reports(
    report_type: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """List all saved reports for the current user."""
    user_id = user["id"]
    offset = (page - 1) * limit
    
    supabase = get_supabase_client()
    
    try:
        query = supabase.table("profile_reports") \
            .select("id, report_type, profile_identifier, profile_name, profile_image, overall_score, created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .range(offset, offset + limit - 1)
        
        if report_type:
            query = query.eq("report_type", report_type)
        
        result = query.execute()
        
        return {
            "reports": result.data or [],
            "page": page,
            "limit": limit,
        }
        
    except Exception as e:
        logger.error("list_reports_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch reports: {str(e)}")


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a specific report by ID."""
    user_id = user["id"]
    
    supabase = get_supabase_client()
    
    try:
        result = supabase.table("profile_reports") \
            .select("*") \
            .eq("id", report_id) \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Report not found")
        
        return result.data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch report: {str(e)}")


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a saved report."""
    user_id = user["id"]
    
    supabase = get_supabase_client()
    
    try:
        # First check ownership
        check = supabase.table("profile_reports") \
            .select("id") \
            .eq("id", report_id) \
            .eq("user_id", user_id) \
            .execute()
        
        if not check.data:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Delete
        supabase.table("profile_reports") \
            .delete() \
            .eq("id", report_id) \
            .execute()
        
        logger.info("delete_report_success", report_id=report_id)
        
        return {"message": "Report deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete report: {str(e)}")
