"""
ResuMax Backend — X (Twitter) Profile Analyzer API
Upload a screenshot of your X/Twitter profile → AI analyzes it and gives suggestions.
"""

import base64
import json
import structlog
from time import time
from fastapi import APIRouter, Depends, UploadFile, File, Form

from app.api.deps import get_current_user
from app.config import get_settings
from app.services.supabase import get_supabase_client

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/x-analyzer", tags=["x-analyzer"])


SYSTEM_PROMPT = """You are an expert X (formerly Twitter) profile analyst. You analyze screenshots with extreme attention to detail.

CRITICAL: LOOK AT THE SCREENSHOT CAREFULLY!
1. If there is a custom banner/header image at the top - describe it
2. If there is a profile photo - analyze its quality and branding
3. READ the bio/description text carefully
4. Look at follower/following counts, engagement metrics
5. Check for pinned tweets, content themes
6. Look at the overall visual branding and consistency

SCORING (be strict):
- Banner/Header: 0 if default gray. Custom banner = 40-100 based on quality
- Profile Photo: Score based on quality, branding, memorability
- Bio: Score based on clarity, value proposition, CTA, link
- Engagement: Score based on visible follower ratio and interaction counts
- Content: Score based on visible tweet quality and consistency

Be ACCURATE. Describe what you actually SEE in the screenshot.

Always return valid JSON."""


ANALYZE_PROMPT = """Analyze this X (Twitter) profile screenshot. LOOK CAREFULLY at what's actually visible.

STEP BY STEP:
1. HEADER/BANNER: Look at the top of the profile. Is there a custom header image?
   - Custom branded image = score 50-90
   - Plain default = score 0, "missing"

2. PROFILE PHOTO: Is there a photo? How memorable/brandable is it?

3. DISPLAY NAME: Read the name. Does it include any branding elements (emojis, titles)?

4. BIO/DESCRIPTION: Read the bio text. Quote it exactly. Does it:
   - Clearly state who they are?
   - Have a value proposition?
   - Include a CTA or link?
   - Use line breaks effectively?

5. PINNED TWEET: Can you see a pinned tweet? What's it about?

6. FOLLOWER METRICS: What are the follower/following counts? Is the ratio healthy?

7. CONTENT SAMPLES: Can you see any recent tweets? What's the tone/quality?

8. PROFILE LINK: Is there a website/link in the profile?

{additional_context}

Return JSON:
{{
  "profile_name": "<EXACT name from profile>",
  "handle": "<@handle if visible>",
  "overall_score": <0-100 average of visible sections>,
  "overall_summary": "<2-3 sentence brutally honest assessment>",
  "sections": [
    {{
      "name": "Header/Banner Image",
      "score": <0 if default, 50-100 if custom based on quality>,
      "status": "<missing|needs_work|good|excellent>",
      "current": "<describe what you see>",
      "suggestions": ["<specific suggestions>"]
    }},
    {{
      "name": "Profile Photo",
      "score": <score>,
      "status": "<status>",
      "current": "<describe: professional headshot, logo, casual, etc>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Display Name",
      "score": <score based on branding effectiveness>,
      "status": "<status>",
      "current": "<EXACT display name>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Bio / Description",
      "score": <score based on clarity, CTA, value prop>,
      "status": "<status>",
      "current": "<EXACT bio text>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Pinned Tweet",
      "score": <0 if no pinned, else score based on strategic value>,
      "status": "<missing|needs_work|good|excellent>",
      "current": "<describe pinned tweet or 'No pinned tweet visible'>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Follower Metrics",
      "score": <score based on ratio and count>,
      "status": "<status>",
      "current": "<followers / following counts>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Content Strategy",
      "score": <score based on visible content quality>,
      "status": "<status>",
      "current": "<describe visible content themes/quality>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Profile Link / CTA",
      "score": <0 if missing, else score>,
      "status": "<status>",
      "current": "<link URL or 'No link visible'>",
      "suggestions": ["<suggestions>"]
    }}
  ],
  "quick_wins": ["<action 1>", "<action 2>", "<action 3>", "<action 4>"],
  "bio_suggestions": ["<bio option 1>", "<bio option 2>", "<bio option 3>"],
  "content_strategy_tips": [
    {{"tip": "<tip>", "why": "<reason>", "how": "<how to implement>"}},
    {{"tip": "<tip>", "why": "<reason>", "how": "<how to implement>"}},
    {{"tip": "<tip>", "why": "<reason>", "how": "<how to implement>"}}
  ],
  "hashtag_recommendations": ["<hashtag1>", "<hashtag2>", "<hashtag3>", "<hashtag4>", "<hashtag5>"],
  "growth_tactics": [
    "<tactic 1 for growing X presence>",
    "<tactic 2>",
    "<tactic 3>"
  ]
}}

BEFORE RESPONDING — VERIFY:
1. Did I look at the banner area? If there's a custom image, it's NOT "missing"
2. Did I read the actual bio text?
3. Am I only marking sections as 0 if truly not visible?"""


@router.post("/analyze")
async def analyze_x_screenshot(
    screenshot: UploadFile = File(...),
    context: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """Analyze an X/Twitter profile screenshot and return optimization suggestions."""
    user_id = user["id"]
    logger.info("x_analyze_start", user_id=user_id, filename=screenshot.filename)

    # Read and encode the image
    image_bytes = await screenshot.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Determine MIME type
    content_type = screenshot.content_type or "image/png"
    if content_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        content_type = "image/png"

    additional_context = ""
    if context.strip():
        additional_context = f"ADDITIONAL CONTEXT FROM USER: {context.strip()}"

    prompt = ANALYZE_PROMPT.format(additional_context=additional_context)

    # Use Groq vision model
    settings = get_settings()

    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)

    start = time()
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{image_base64}",
                            },
                        },
                    ],
                },
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        elapsed = int((time() - start) * 1000)
        raw_text = response.choices[0].message.content
        logger.info("x_vision_complete", elapsed_ms=elapsed, chars=len(raw_text))
    except Exception as e:
        logger.error("x_vision_failed", error=str(e))
        raise

    # Parse JSON from response
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1
        if start_idx != -1 and end_idx > start_idx:
            result = json.loads(text[start_idx:end_idx])
        else:
            raise ValueError("Failed to parse vision model response as JSON")

    # Save to database
    try:
        supabase = get_supabase_client()
        supabase.table("profile_reports").insert({
            "user_id": user_id,
            "report_type": "x_twitter",
            "profile_identifier": result.get("handle", "unknown"),
            "profile_name": result.get("profile_name", "X Profile"),
            "overall_score": result.get("overall_score", 0),
            "report_data": result,
        }).execute()
        logger.info("x_report_saved", user_id=user_id)
    except Exception as e:
        logger.warning("x_report_save_failed", error=str(e))

    logger.info("x_analyze_complete", user_id=user_id, score=result.get("overall_score"))
    return result
