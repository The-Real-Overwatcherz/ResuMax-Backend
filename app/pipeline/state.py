"""
ResuMax — Pipeline State
Shared TypedDict used across all LangGraph nodes.
"""

from typing import TypedDict, Optional, List
from app.models.resume import ParsedResume
from app.models.analysis import (
    ATSBreakdown, KeywordMatch, DeepAnalysis, SkillAnalysis,
    InterviewQuestion, BulletRewrite, DensityAnalysis, ShrutiSuggestion,
)


class PipelineState(TypedDict):
    """Shared state passed through all pipeline nodes."""

    # === INPUTS ===
    resume_text: str
    resume_file_path: str
    job_description: str
    user_id: str
    analysis_id: str

    # === NODE 1: Parser ===
    parsed_resume: Optional[dict]         # ParsedResume.model_dump()

    # === NODE 2: ATS Scorer ===
    ats_score: Optional[int]
    ats_breakdown: Optional[dict]         # ATSBreakdown.model_dump()
    keyword_matches: Optional[List[dict]] # List of KeywordMatch dicts
    total_keywords_found: Optional[int]
    total_keywords_missing: Optional[int]

    # === NODE 3: Deep Analyzer ===
    deep_analysis: Optional[dict]         # DeepAnalysis.model_dump()

    # === NODE 3b: Skill Matcher ===
    skill_analysis: Optional[dict]        # SkillAnalysis.model_dump()

    # === NODE 4: AI Interviewer ===
    interview_questions: Optional[List[dict]]

    # === NODE 5: Bullet Rewriter ===
    bullet_rewrites: Optional[List[dict]]
    total_bullets_rewritten: Optional[int]

    # === NODE 5b: Density Checker ===
    density_analysis: Optional[dict]      # DensityAnalysis.model_dump()

    # === NODE 6: Final Optimizer ===
    optimized_resume: Optional[dict]      # ParsedResume.model_dump()
    final_ats_score: Optional[int]
    score_improvement: Optional[int]

    # === SHRUTI ===
    shruti_suggestions: Optional[List[dict]]

    # === PIPELINE META ===
    current_step: int
    status: str
    errors: List[str]
    processing_start_time: Optional[float]
    node_timings: dict                    # {node_name: elapsed_ms}
