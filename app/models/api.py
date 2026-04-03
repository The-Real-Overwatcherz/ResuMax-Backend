"""
ResuMax — API Request/Response Schemas
Pydantic models for API endpoint validation.
"""

from typing import Optional, List, Any
from pydantic import BaseModel, Field


# ── Analysis Endpoints ───────────────────────────────────────────

class AnalysisStartResponse(BaseModel):
    """Response from POST /api/analysis/start"""
    analysis_id: str
    status: str = "pending"
    message: str = "Analysis pipeline started. Subscribe to realtime channel for updates."
    realtime_channel: str


class AnalysisStatusResponse(BaseModel):
    """Response from GET /api/analysis/{id}/status"""
    status: str
    current_step: int
    total_steps: int = 8
    step_label: str
    estimated_remaining_seconds: Optional[int] = None


class AnalysisResultResponse(BaseModel):
    """Response from GET /api/analysis/{id}"""
    id: str
    status: str
    created_at: str

    # ATS
    ats_score: Optional[int] = None
    ats_breakdown: Optional[dict] = None

    # Keywords
    keyword_analysis: Optional[dict] = None

    # Skills
    skill_analysis: Optional[dict] = None

    # Deep Analysis
    deep_analysis: Optional[dict] = None

    # Bullet Rewrites
    bullet_rewrites: Optional[List[dict]] = None

    # Density
    density_analysis: Optional[dict] = None

    # Interview Questions
    interview_questions: Optional[List[dict]] = None

    # Optimized Resume
    optimized_resume: Optional[dict] = None
    final_ats_score: Optional[int] = None
    score_improvement: Optional[int] = None

    # SHRUTI
    shruti_available: bool = False
    total_suggestions: int = 0

    # Meta
    processing_time_ms: Optional[int] = None
    model_used: Optional[str] = None


# ── History Endpoint ─────────────────────────────────────────────

class AnalysisHistoryItem(BaseModel):
    """Single item in history list."""
    id: str
    job_title: Optional[str] = None
    ats_score: Optional[int] = None
    final_ats_score: Optional[int] = None
    status: str
    created_at: str


class HistoryResponse(BaseModel):
    """Response from GET /api/history"""
    analyses: List[AnalysisHistoryItem]
    total: int
    page: int
    limit: int
