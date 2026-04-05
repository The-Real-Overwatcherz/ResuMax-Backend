"""
ResuMax Backend — Skill Gap Heatmap API
Analyzes resume against multiple job descriptions to find skill coverage patterns.
"""

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.services.groq_client import get_groq_balanced, get_groq_fast, call_llm_with_fallback
from app.services.behavior_profiler import get_or_analyze_profile, build_adaptive_prompt

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/skill-gap", tags=["skill-gap"])


class SkillGapRequest(BaseModel):
    resume_text: str
    job_descriptions: list[dict]  # [{"title": "SWE at Google", "description": "..."}]


SYSTEM_PROMPT = """You are Shruti, ResuMax's AI Skill Analyst. You analyze a resume against multiple job descriptions to produce a skill gap heatmap.

You MUST return a valid JSON object with this exact structure:
{
  "skills": [
    {
      "name": "Skill name (e.g., Python, System Design, Docker)",
      "category": "technical" | "soft" | "tool" | "certification",
      "coverage": [
        {
          "job_index": 0,
          "status": "strong" | "partial" | "missing" | "not_required",
          "evidence": "Brief explanation of why"
        }
      ],
      "resume_has": true | false,
      "importance": "critical" | "important" | "nice_to_have"
    }
  ],
  "summary": {
    "total_skills_analyzed": 0,
    "strong_matches": 0,
    "partial_matches": 0,
    "missing_skills": 0,
    "overall_readiness_percent": 0
  },
  "priority_actions": [
    {
      "skill": "Skill name",
      "why": "Why this matters most",
      "how": "Fastest way to acquire it",
      "impact": "How many of the target jobs need it (e.g., 4/5)"
    }
  ],
  "hidden_strengths": [
    "Skills the resume has that none of the JDs mention but are valuable"
  ]
}

Rules:
- Extract ALL skills mentioned across ALL job descriptions
- For each skill, check if the resume demonstrates it (strong), hints at it (partial), or lacks it (missing)
- If a JD doesn't require a skill, mark it "not_required"
- Order skills by how many JDs require them (most common first)
- Limit to top 20 most impactful skills
- priority_actions should be the 3-5 skills with highest ROI to learn
- Return ONLY valid JSON, no markdown fences"""


@router.post("/analyze")
async def analyze_skill_gaps(
    request: SkillGapRequest,
    user: dict = Depends(get_current_user),
):
    """Analyze skill gaps across multiple job descriptions."""
    logger.info("skill_gap_analyze", user_id=user["id"], num_jds=len(request.job_descriptions))

    if not request.job_descriptions or len(request.job_descriptions) > 6:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Provide 1-6 job descriptions")

    # Behavioral adaptation
    adaptive_prompt = build_adaptive_prompt(SYSTEM_PROMPT,
        await get_or_analyze_profile(user["id"], [{"role": "user", "content": "skill gap analysis"}])
    )

    # Format JDs
    jds_text = ""
    for i, jd in enumerate(request.job_descriptions):
        jds_text += f"\n--- JOB {i + 1}: {jd.get('title', f'Job {i+1}')} ---\n{jd['description'][:2000]}\n"

    prompt = f"""CANDIDATE'S RESUME:
{request.resume_text[:4000]}

JOB DESCRIPTIONS TO COMPARE AGAINST:
{jds_text}

Analyze the skill gaps across all {len(request.job_descriptions)} job descriptions. Return the JSON heatmap data."""

    result = await call_llm_with_fallback(
        primary=get_groq_balanced(),
        fallback=get_groq_fast(),
        prompt=prompt,
        system_prompt=adaptive_prompt,
        parse_json=True,
    )

    # Attach job titles for frontend reference
    result["job_titles"] = [jd.get("title", f"Job {i+1}") for i, jd in enumerate(request.job_descriptions)]
    return result
