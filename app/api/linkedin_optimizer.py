"""
ResuMax Backend — LinkedIn Optimizer API
AI-powered LinkedIn profile optimization and content strategy.
"""

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user
from app.services.groq_client import (
    get_groq_balanced,
    get_groq_fast,
    call_llm_with_fallback,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/linkedin-optimizer", tags=["linkedin-optimizer"])


class LinkedInOptimizeRequest(BaseModel):
    full_name: str
    current_role: str = ""
    industry: str = ""
    experience_summary: str = ""
    skills: list[str] = []
    current_headline: str = ""
    current_about: str = ""
    target_audience: str = ""
    goals: str = ""


SYSTEM_PROMPT = """You are an elite LinkedIn growth strategist and personal branding expert.
You help professionals optimize their LinkedIn presence for maximum visibility, engagement, and career growth.
You understand LinkedIn's algorithm deeply — how it ranks content, boosts engagement, and surfaces profiles in search.
Always return valid JSON matching the requested schema. No markdown outside JSON."""


OPTIMIZE_PROMPT = """Analyze this professional's profile and generate a COMPLETE LinkedIn optimization strategy.

PROFESSIONAL PROFILE:
- Name: {full_name}
- Current Role: {current_role}
- Industry: {industry}
- Experience: {experience_summary}
- Skills: {skills}
- Current Headline: {current_headline}
- Current About: {current_about}
- Target Audience: {target_audience}
- Goals: {goals}

Return a JSON object with this EXACT structure:
{{
  "profile_optimization": {{
    "headline_options": [
      "headline option 1 (max 220 chars, keyword-rich)",
      "headline option 2",
      "headline option 3"
    ],
    "about_section": "A compelling 2000-char max About section in first person. Conversational, keyword-rich, with a clear CTA. Use line breaks for readability.",
    "experience_tips": [
      "Specific tip for improving their experience section",
      "Another tip"
    ],
    "profile_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
  }},
  "content_calendar": {{
    "best_posting_times": [
      {{"day": "Tuesday", "time": "8:00 AM", "reason": "Why this time works"}},
      {{"day": "Wednesday", "time": "12:00 PM", "reason": "Why this time works"}},
      {{"day": "Thursday", "time": "7:30 AM", "reason": "Why this time works"}}
    ],
    "posting_frequency": "How often they should post per week with reasoning",
    "content_mix": [
      {{"type": "Personal Story", "percentage": 30, "description": "Why and what kind"}},
      {{"type": "Industry Insights", "percentage": 25, "description": "Why and what kind"}},
      {{"type": "How-to / Tips", "percentage": 20, "description": "Why and what kind"}},
      {{"type": "Engagement Posts", "percentage": 15, "description": "Why and what kind"}},
      {{"type": "Achievements / Wins", "percentage": 10, "description": "Why and what kind"}}
    ]
  }},
  "post_ideas": [
    {{
      "title": "Post idea title",
      "hook": "The first 2 lines that appear before 'see more' — must be scroll-stopping",
      "outline": "Brief outline of the full post (3-5 bullet points)",
      "format": "text / carousel / poll / video / document",
      "best_day": "Tuesday"
    }},
    {{
      "title": "Post idea 2",
      "hook": "Hook line",
      "outline": "Outline",
      "format": "format type",
      "best_day": "Day"
    }},
    {{
      "title": "Post idea 3",
      "hook": "Hook line",
      "outline": "Outline",
      "format": "format type",
      "best_day": "Day"
    }},
    {{
      "title": "Post idea 4",
      "hook": "Hook line",
      "outline": "Outline",
      "format": "format type",
      "best_day": "Day"
    }},
    {{
      "title": "Post idea 5",
      "hook": "Hook line",
      "outline": "Outline",
      "format": "format type",
      "best_day": "Day"
    }}
  ],
  "post_templates": [
    {{
      "name": "Template name (e.g. 'The Lesson Learned')",
      "template": "Full ready-to-post content with placeholders in [brackets] where they should customize. Include emojis, line breaks, and formatting.",
      "when_to_use": "When to use this template"
    }},
    {{
      "name": "Template 2",
      "template": "Full template text",
      "when_to_use": "When to use"
    }},
    {{
      "name": "Template 3",
      "template": "Full template text",
      "when_to_use": "When to use"
    }}
  ],
  "hashtag_strategy": {{
    "primary_hashtags": ["5 high-volume hashtags relevant to their industry"],
    "niche_hashtags": ["5 lower-competition niche hashtags for their specific role"],
    "branded_hashtags": ["2-3 personal brand hashtag suggestions"],
    "usage_tips": "How many hashtags to use per post and where to place them"
  }},
  "engagement_tips": [
    {{
      "tip": "Specific actionable engagement tip",
      "why": "Why this works with LinkedIn's algorithm",
      "action": "Exact action to take today"
    }},
    {{
      "tip": "Tip 2",
      "why": "Reasoning",
      "action": "Action"
    }},
    {{
      "tip": "Tip 3",
      "why": "Reasoning",
      "action": "Action"
    }},
    {{
      "tip": "Tip 4",
      "why": "Reasoning",
      "action": "Action"
    }},
    {{
      "tip": "Tip 5",
      "why": "Reasoning",
      "action": "Action"
    }}
  ]
}}

Be specific to their industry, role, and goals. No generic advice. Every recommendation should be actionable."""


@router.post("/optimize")
async def optimize_linkedin(
    request: LinkedInOptimizeRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a full LinkedIn optimization strategy."""
    logger.info("linkedin_optimize_start", user_id=user["id"], role=request.current_role)

    prompt = OPTIMIZE_PROMPT.format(
        full_name=request.full_name,
        current_role=request.current_role or "Not specified",
        industry=request.industry or "Not specified",
        experience_summary=request.experience_summary[:3000] or "Not provided",
        skills=", ".join(request.skills[:20]) if request.skills else "Not provided",
        current_headline=request.current_headline or "Not provided",
        current_about=request.current_about or "Not provided",
        target_audience=request.target_audience or "Not specified",
        goals=request.goals or "Grow LinkedIn presence and career opportunities",
    )

    result = await call_llm_with_fallback(
        primary=get_groq_balanced(),
        fallback=get_groq_fast(),
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        parse_json=True,
    )

    logger.info("linkedin_optimize_complete", user_id=user["id"])
    return result
