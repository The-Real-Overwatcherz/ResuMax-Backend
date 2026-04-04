"""
ResuMax Backend — Social Post Generator API
Generate platform-specific posts for both LinkedIn and X (Twitter) simultaneously.
Shruti guides the user through topic → content → tone → dual-platform posts.
"""

import json
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.api.deps import get_current_user
from app.services.groq_client import get_groq_balanced, get_groq_fast, call_llm_with_fallback
from app.services.supabase import get_supabase_client

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/social-post", tags=["social-post"])


class GeneratePostRequest(BaseModel):
    topic: str
    key_points: str = ""
    tone: str = "professional"  # professional, casual, inspirational, technical, humorous
    target_audience: str = ""
    include_thread: bool = False  # Generate X thread if content is long


SYSTEM_PROMPT = """You are Shruti, an elite social media strategist who creates viral, high-engagement posts.
You understand the FUNDAMENTAL DIFFERENCES between LinkedIn and X (Twitter):

LINKEDIN:
- Professional networking platform
- Longer format (up to 3000 chars)
- Storytelling works incredibly well
- Use line breaks for readability
- Hook in the first 2 lines (before "see more")
- Use 3-5 relevant hashtags at the END
- Professional but human tone
- Value-driven content performs best
- Use emojis sparingly (1-3 max)
- Include a call-to-action or question

X (TWITTER):
- Fast-paced, concise, punchy
- 280 character limit per tweet
- Threads for deeper content (each tweet ≤ 280 chars)
- Hook must be in the FIRST tweet
- Use 2-3 trending/relevant hashtags max
- More casual, witty, direct tone
- Hot takes and opinions perform well
- Use of line breaks for impact
- Engagement bait works (polls, questions)
- Emojis can be used more freely

CRITICAL: These posts must be DISTINCTLY DIFFERENT — not just the same text shortened/lengthened.
The LinkedIn post should leverage storytelling, professional context, and value-sharing.
The X post should be punchy, opinion-driven, and viral-optimized.

Always return valid JSON."""


GENERATE_PROMPT = """Create TWO distinct social media posts about the following topic.
These posts should be COMPLETELY DIFFERENT in style, structure, and approach — each optimized for its platform.

TOPIC: {topic}

KEY POINTS TO INCLUDE: {key_points}

TONE: {tone}

TARGET AUDIENCE: {target_audience}

{thread_instruction}

Return JSON with this exact structure:
{{
  "linkedin_post": {{
    "content": "<full LinkedIn post text with proper line breaks using \\n>",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
    "character_count": <number>,
    "hook_line": "<the first 2 lines that appear before 'see more'>",
    "engagement_tips": [
      "<tip 1 for maximizing LinkedIn engagement>",
      "<tip 2>",
      "<tip 3>"
    ],
    "best_posting_time": "<recommended time to post on LinkedIn>",
    "image_recommendation": {{
      "should_attach": <true/false>,
      "suggested_image": "<describe what kind of image would boost this post>",
      "image_type": "<infographic|photo|carousel|document|none>"
    }}
  }},
  "x_post": {{
    "content": "<main tweet text, MUST be ≤ 280 characters>",
    "hashtags": ["hashtag1", "hashtag2", "hashtag3"],
    "character_count": <number>,
    "thread": [
      "<tweet 1 text (≤280 chars)>",
      "<tweet 2 text (≤280 chars)>"
    ],
    "is_thread": <true if thread has more than 1 tweet>,
    "engagement_tips": [
      "<tip 1 for maximizing X engagement>",
      "<tip 2>",
      "<tip 3>"
    ],
    "best_posting_time": "<recommended time to post on X>",
    "image_recommendation": {{
      "should_attach": <true/false>,
      "suggested_image": "<describe what kind of image would boost this post>",
      "image_type": "<meme|infographic|screenshot|photo|none>"
    }}
  }},
  "topic_summary": "<1 sentence summary of what these posts are about>",
  "virality_score": <1-10 rating of how viral this content could go>,
  "platform_strategy": "<1-2 sentences on why the posts are different>"
}}

RULES:
1. LinkedIn post must be 500-2000 characters — use storytelling, hook readers
2. X post main tweet MUST be ≤ 280 characters — be concise and punchy
3. Posts must feel like they were written by DIFFERENT people — LinkedIn is a thought leader, X is a sharp commentator
4. Include actual hashtags without # prefix in the arrays
5. If thread is requested, create 3-5 tweets that tell a story
6. Hashtags should be relevant and some should be trending/popular"""


@router.post("/generate")
async def generate_social_posts(
    request: GeneratePostRequest,
    user: dict = Depends(get_current_user),
):
    """Generate platform-specific posts for LinkedIn and X simultaneously."""
    user_id = user["id"]

    logger.info(
        "social_post_generate_start",
        user_id=user_id,
        topic=request.topic[:50],
        tone=request.tone,
    )

    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Topic is required")

    thread_instruction = ""
    if request.include_thread:
        thread_instruction = "IMPORTANT: Generate a full X THREAD with 3-5 tweets that tell a complete story. Each tweet must be ≤ 280 characters."
    else:
        thread_instruction = "For the X post, provide a single punchy tweet. Only include a thread array with 1 element (the main tweet)."

    prompt = GENERATE_PROMPT.format(
        topic=request.topic.strip(),
        key_points=request.key_points.strip() or "No specific points — use your judgment based on the topic",
        tone=request.tone,
        target_audience=request.target_audience.strip() or "General professional audience",
        thread_instruction=thread_instruction,
    )

    try:
        result = await call_llm_with_fallback(
            primary=get_groq_balanced(),
            fallback=get_groq_fast(),
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            parse_json=True,
        )
    except Exception as e:
        logger.error("social_post_generate_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate posts: {str(e)}")

    logger.info(
        "social_post_generate_complete",
        user_id=user_id,
        virality_score=result.get("virality_score"),
    )

    # Save to database
    try:
        supabase = get_supabase_client()
        supabase.table("profile_reports").insert({
            "user_id": user_id,
            "report_type": "social_post",
            "profile_identifier": request.topic[:100],
            "profile_name": f"Post: {request.topic[:80]}",
            "overall_score": result.get("virality_score", 0) * 10,  # Scale 1-10 to 10-100
            "report_data": {
                "topic": request.topic,
                "key_points": request.key_points,
                "tone": request.tone,
                "target_audience": request.target_audience,
                "result": result,
            },
        }).execute()
        logger.info("social_post_saved", user_id=user_id)
    except Exception as e:
        logger.warning("social_post_save_failed", error=str(e))
        # Don't fail the request if save fails

    return result
