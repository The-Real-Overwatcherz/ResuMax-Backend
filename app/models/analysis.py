"""
ResuMax — Analysis Pydantic Models
Structured output models for all pipeline nodes.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


# ── Node 2: ATS Scoring ─────────────────────────────────────────

class KeywordMatch(BaseModel):
    """Single keyword match result."""
    keyword: str
    found: bool
    location: Optional[str] = None          # "skills", "experience.bullet.3"
    importance: str = "important"           # "critical", "important", "nice-to-have"
    jd_frequency: int = 1


class ATSBreakdown(BaseModel):
    """Multi-factor ATS score breakdown."""
    keyword_score: float = 0                # 0-100, weight: 40%
    section_completeness: float = 0         # 0-100, weight: 15%
    format_compliance: float = 0            # 0-100, weight: 10%
    action_verb_usage: float = 0            # 0-100, weight: 15%
    quantification_rate: float = 0          # 0-100, weight: 20%
    final_score: int = 0                    # Weighted average


# ── Node 3: Deep Analysis ───────────────────────────────────────

class DeepAnalysis(BaseModel):
    """Holistic resume quality assessment."""
    experience_level_match: str = "match"   # "under-qualified", "match", "over-qualified"
    industry_alignment: float = 0           # 0-100
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    gap_analysis: List[dict] = Field(default_factory=list)  # [{area, gap_description, suggestion}]
    overall_assessment: str = ""


# ── Node 3b: Skill Matching ─────────────────────────────────────

class SkillAnalysis(BaseModel):
    """Semantic skill matching results."""
    exact_matches: List[str] = Field(default_factory=list)
    synonym_matches: List[dict] = Field(default_factory=list)   # [{resume, jd}]
    implicit_skills: List[dict] = Field(default_factory=list)   # [{skill, evidence}]
    missing_critical: List[str] = Field(default_factory=list)
    missing_optional: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


# ── Node 4: Interview Questions ─────────────────────────────────

class InterviewQuestion(BaseModel):
    """Targeted question for weak/vague bullet points."""
    question: str
    target_bullet: str
    purpose: str = "quantification"         # "quantification", "context", "impact", "tools"
    company: str = ""


# ── Node 5: Bullet Rewrites ─────────────────────────────────────

class BulletRewrite(BaseModel):
    """Single bullet point rewrite with metadata."""
    original: str
    rewritten: str
    company: str = ""
    improvement_type: str = "star-format"   # "quantified", "action-verb", "star-format", "keyword-injected"
    keywords_added: List[str] = Field(default_factory=list)
    confidence: float = 0.8
    reasoning: str = ""


# ── Node 5b: Density Analysis ───────────────────────────────────

class DensityAnalysis(BaseModel):
    """Post-rewrite keyword density validation."""
    keyword_density_scores: List[dict] = Field(default_factory=list)  # [{keyword, count, optimal, score}]
    overall_density_score: float = 0
    over_stuffed_keywords: List[str] = Field(default_factory=list)
    under_represented: List[str] = Field(default_factory=list)
    formatting_issues: List[str] = Field(default_factory=list)


# ── SHRUTI Suggestions ──────────────────────────────────────────

class ShrutiSuggestion(BaseModel):
    """Interactive suggestion card for SHRUTI advisor."""
    id: str
    category: str                           # "bullet_rewrite", "keyword_injection", "skill_addition",
                                            # "section_reorder", "format_fix", "quantification"
    title: str
    description: str
    before: Optional[str] = None
    after: Optional[str] = None
    impact: str = "medium"                  # "high", "medium", "low"
    estimated_score_change: int = 0
    accepted: Optional[bool] = None
