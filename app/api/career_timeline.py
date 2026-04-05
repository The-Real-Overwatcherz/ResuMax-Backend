"""
ResuMax Backend — Career Timeline Visualizer API
Parses resume to generate an interactive career trajectory with growth, gaps, and pivots.
"""

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.services.groq_client import get_groq_balanced, get_groq_fast, call_llm_with_fallback
from app.services.behavior_profiler import get_or_analyze_profile, build_adaptive_prompt

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/career-timeline", tags=["career-timeline"])


class TimelineRequest(BaseModel):
    resume_text: str


SYSTEM_PROMPT = """You are Shruti, ResuMax's AI Career Analyst. You parse resumes to create a visual career timeline showing the full trajectory of someone's professional journey.

You MUST return a valid JSON object with this exact structure:
{
  "timeline": [
    {
      "type": "role" | "education" | "gap" | "pivot" | "freelance" | "project",
      "title": "Job title or degree or description",
      "organization": "Company or university name",
      "start_date": "YYYY-MM or YYYY",
      "end_date": "YYYY-MM or Present",
      "duration_months": 24,
      "description": "1-2 sentence summary of what they did",
      "skills_gained": ["skill1", "skill2"],
      "growth_indicator": "promotion" | "lateral" | "step_up" | "career_change" | "entry" | "gap" | "education",
      "impact_level": 1-5
    }
  ],
  "career_analysis": {
    "total_years": 0,
    "num_roles": 0,
    "num_companies": 0,
    "career_trajectory": "ascending" | "stable" | "pivoting" | "early_stage",
    "avg_tenure_months": 0,
    "longest_tenure": {"company": "", "months": 0},
    "shortest_tenure": {"company": "", "months": 0},
    "gaps": [
      {
        "start": "YYYY-MM",
        "end": "YYYY-MM",
        "duration_months": 0,
        "concern_level": "none" | "minor" | "notable",
        "suggestion": "How to address this in interviews"
      }
    ],
    "pivots": [
      {
        "from_role": "",
        "to_role": "",
        "when": "YYYY",
        "type": "industry_change" | "role_change" | "level_change",
        "narrative": "How to frame this positively"
      }
    ]
  },
  "growth_score": 0-100,
  "narrative": "A 2-3 sentence story of this person's career journey",
  "recommendations": [
    "What they should do next based on their trajectory"
  ]
}

Rules:
- Parse ALL roles, education, projects from the resume
- Order timeline chronologically (oldest first)
- Detect gaps between roles (>2 months = gap)
- Detect career pivots (different industry or role type)
- Calculate accurate durations
- growth_score: 0-100 based on trajectory, promotions, skill growth
- Be specific with dates — use what's on the resume
- If dates are ambiguous, make reasonable estimates
- Return ONLY valid JSON, no markdown fences"""


@router.post("/analyze")
async def analyze_career_timeline(
    request: TimelineRequest,
    user: dict = Depends(get_current_user),
):
    """Parse resume and generate career timeline data."""
    logger.info("career_timeline_analyze", user_id=user["id"])

    adaptive_prompt = build_adaptive_prompt(SYSTEM_PROMPT,
        await get_or_analyze_profile(user["id"], [{"role": "user", "content": "career timeline"}])
    )

    prompt = f"""RESUME TO ANALYZE:
{request.resume_text[:5000]}

Parse this resume and generate a complete career timeline with all roles, education, gaps, and pivots. Calculate growth trajectory and provide career narrative. Return the JSON."""

    result = await call_llm_with_fallback(
        primary=get_groq_balanced(),
        fallback=get_groq_fast(),
        prompt=prompt,
        system_prompt=adaptive_prompt,
        parse_json=True,
    )

    return result
