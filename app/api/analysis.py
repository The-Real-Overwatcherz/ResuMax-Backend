"""
ResuMax — Analysis API Routes
Upload resume + start pipeline, get results, check status.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.api.deps import get_current_user
from app.services.file_parser import parse_resume_file
from app.services.doc_generator import generate_optimized_resume
from app.services.supabase import (
    create_analysis, get_analysis, upload_resume, get_user_analyses, delete_analysis
)
from app.pipeline.graph import run_pipeline

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# Step labels for status endpoint
STEP_LABELS = {
    0: "Queued",
    1: "Extracting resume data",
    2: "Calculating ATS score",
    3: "Running deep analysis",
    4: "Generating interview questions",
    5: "Rewriting bullet points",
    6: "Optimization complete",
}

# Max file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@router.post("/start")
async def start_analysis(
    background_tasks: BackgroundTasks,
    resume: UploadFile = File(...),
    job_description: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """
    Upload a resume file + job description to start the analysis pipeline.
    Returns immediately with analysis_id + realtime channel.
    Pipeline runs in the background.
    """
    user_id = user["id"]

    # ── Validate file type ──
    filename = resume.filename or "upload.pdf"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Accepted: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # ── Read and validate file size ──
    file_bytes = await resume.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    # ── Validate job description ──
    if not job_description or len(job_description.strip()) < 20:
        raise HTTPException(status_code=400, detail="Job description is too short. Please provide the full JD.")

    # ── Extract text from resume ──
    try:
        resume_text = parse_resume_file(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Create analysis record in DB ──
    analysis_record = await create_analysis(
        user_id=user_id,
        resume_file_path="",  # Will be updated after upload
        resume_text=resume_text,
        job_description=job_description.strip(),
        job_title="",  # Could extract from JD later
    )
    analysis_id = analysis_record["id"]

    # ── Upload file to Supabase Storage ──
    try:
        storage_path = await upload_resume(user_id, analysis_id, file_bytes, filename)
    except Exception as e:
        logger.warning("storage_upload_failed", error=str(e))
        storage_path = ""

    # ── Start pipeline in background ──
    background_tasks.add_task(
        run_pipeline,
        analysis_id=analysis_id,
        resume_text=resume_text,
        job_description=job_description.strip(),
        user_id=user_id,
        resume_file_path=storage_path,
    )

    logger.info("analysis_started", analysis_id=analysis_id, user_id=user_id)

    return {
        "analysis_id": analysis_id,
        "status": "pending",
        "message": "Analysis pipeline started. Subscribe to realtime channel for updates.",
        "realtime_channel": f"analysis:{analysis_id}",
    }


@router.get("/")
async def list_analyses(
    page: int = 1,
    limit: int = 10,
    user: dict = Depends(get_current_user),
):
    """List all past analyses for the current user."""
    return await get_user_analyses(user["id"], page=page, limit=limit)


@router.get("/{analysis_id}")
async def get_analysis_results(
    analysis_id: str,
    user: dict = Depends(get_current_user),
):
    """Get full analysis results."""
    analysis = await get_analysis(analysis_id)

    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if analysis.get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Calculate SHRUTI availability
    shruti_suggestions = analysis.get("shruti_suggestions") or []

    return {
        "id": analysis["id"],
        "status": analysis.get("status", "pending"),
        "created_at": str(analysis.get("created_at", "")),

        # ATS
        "ats_score": analysis.get("ats_score"),
        "ats_breakdown": analysis.get("ats_breakdown"),

        # Keywords
        "keyword_analysis": analysis.get("keyword_analysis"),

        # Skills
        "skill_analysis": analysis.get("skill_analysis"),

        # Deep Analysis
        "deep_analysis": analysis.get("deep_analysis"),

        # Bullet Rewrites
        "bullet_rewrites": analysis.get("star_rewrites"),

        # Density
        "density_analysis": analysis.get("density_analysis"),

        # Optimized Resume
        "optimized_resume": analysis.get("optimized_resume"),
        "final_ats_score": analysis.get("optimized_resume", {}).get("final_ats_score") if analysis.get("optimized_resume") else None,
        "score_improvement": None,

        # SHRUTI
        "shruti_available": len(shruti_suggestions) > 0,
        "total_suggestions": len(shruti_suggestions),

        # Meta
        "processing_time_ms": analysis.get("processing_time_ms"),
        "model_used": analysis.get("model_used"),
        
        # Context for Voice Chat
        "resume_text": analysis.get("resume_text"),
        "job_description": analysis.get("job_description"),
        "parsed_resume": analysis.get("parsed_resume"),
    }


@router.delete("/{analysis_id}")
async def delete_analysis_endpoint(
    analysis_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a past analysis."""
    analysis = await get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    
    if analysis.get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied.")

    await delete_analysis(analysis_id)
    return {"status": "success", "message": "Analysis deleted."}


@router.get("/{analysis_id}/status")
async def get_analysis_status(
    analysis_id: str,
    user: dict = Depends(get_current_user),
):
    """Lightweight status poll — returns current step and label."""
    analysis = await get_analysis(analysis_id)

    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if analysis.get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied.")

    current_step = analysis.get("current_step", 0)
    status = analysis.get("status", "pending")

    # Estimate remaining time (rough: ~8s per remaining step)
    remaining_steps = max(0, 6 - current_step)
    estimated_remaining = remaining_steps * 8 if status not in ("completed", "failed") else 0

    return {
        "status": status,
        "current_step": current_step,
        "total_steps": 6,
        "step_label": STEP_LABELS.get(current_step, "Processing..."),
        "estimated_remaining_seconds": estimated_remaining,
    }


@router.get("/{analysis_id}/download")
async def download_optimized_resume(
    analysis_id: str,
    user: dict = Depends(get_current_user),
):
    """Download the optimized resume as a DOCX file."""
    analysis = await get_analysis(analysis_id)

    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if analysis.get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied.")

    if analysis.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Analysis is not complete yet.")

    optimized_resume = analysis.get("optimized_resume")
    if not optimized_resume:
        # Fallback: use the parsed resume if optimizer failed
        optimized_resume = analysis.get("parsed_resume", {})

    buffer = generate_optimized_resume(
        optimized_resume=optimized_resume,
        analysis_data=analysis,
    )

    # Build filename from contact name
    contact_name = "Optimized_Resume"
    if isinstance(optimized_resume, dict):
        contact = optimized_resume.get("contact", {})
        if isinstance(contact, dict) and contact.get("full_name"):
            contact_name = contact["full_name"].replace(" ", "_")

    filename = f"{contact_name}_ResuMax.docx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
