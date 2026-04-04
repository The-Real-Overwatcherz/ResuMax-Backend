"""
ResuMax Backend — LinkedIn Optimizer API
Upload a screenshot of your LinkedIn profile → AI analyzes it and gives suggestions.
"""

import base64
import json
import structlog
from time import time
from fastapi import APIRouter, Depends, UploadFile, File, Form
from typing import Optional

from app.api.deps import get_current_user
from app.config import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/linkedin-optimizer", tags=["linkedin-optimizer"])


SYSTEM_PROMPT = """You are an expert LinkedIn profile analyst. You analyze screenshots with extreme attention to detail.

CRITICAL: LOOK AT THE SCREENSHOT CAREFULLY!
1. If there is a banner with colors, images, or text at the top - that's a CUSTOM BANNER (not default gray)
2. If there is a profile photo of a person - analyze its quality
3. READ the headline text that appears below the name
4. Look for About, Experience, Education sections - describe what you see

SCORING:
- Banner: 0 ONLY if it's plain gray/default. Any custom image/color = 50-100
- Photo: Score based on professionalism (good lighting, clear face = higher)
- Sections not visible in screenshot = mark as "not_visible" with score 0

Be ACCURATE. Don't say "no banner" if there clearly IS a banner image visible.

Always return valid JSON."""


ANALYZE_PROMPT = """Analyze this LinkedIn profile screenshot. LOOK CAREFULLY at what's actually visible.

STEP BY STEP:
1. BANNER: Look at the TOP of the profile. Is there a colored/image banner, or plain gray?
   - If you see ANY custom image, colors, text overlay = it's a CUSTOM BANNER (score 50-90)
   - Only plain gray background = "missing" (score 0)

2. PROFILE PHOTO: Is there a photo? How professional does it look?

3. HEADLINE: Read the text below the person's name. Quote it exactly.

4. ABOUT SECTION: Can you see an "About" section? If yes, summarize it.

5. EXPERIENCE: Can you see an "Experience" section? List any visible jobs.

6. EDUCATION: Can you see an "Education" section? List any visible schools.

7. SKILLS: Can you see skills listed?

{additional_context}

Return JSON:
{{
  "profile_name": "<EXACT name of the person from profile>",
  "overall_score": <average of visible sections>,
  "overall_summary": "<2-3 sentence assessment>",
  "sections": [
    {{
      "name": "Banner Image",
      "score": <0 if plain gray, 50-100 if custom image/colors visible>,
      "status": "<missing|needs_work|good|excellent>",
      "current": "<describe what you see: colors, images, text, or 'Plain gray default'>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Profile Photo",
      "score": <score>,
      "status": "<status>",
      "current": "<describe: professional headshot, casual, etc>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Headline",
      "score": <score>,
      "status": "<status>",
      "current": "<EXACT TEXT of the headline>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "About Section",
      "score": <0 if not visible, else score based on content>,
      "status": "<not_visible|missing|needs_work|good|excellent>",
      "current": "<summarize or 'Not visible in screenshot'>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Experience",
      "score": <0 if not visible, else score>,
      "status": "<status>",
      "current": "<list visible jobs or 'Not visible in screenshot'>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Education",
      "score": <0 if not visible, else score>,
      "status": "<status>",
      "current": "<list visible schools or 'Not visible in screenshot'>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Skills & Endorsements",
      "score": <0 if not visible, else score>,
      "status": "<status>",
      "current": "<list skills or 'Not visible'>",
      "suggestions": ["<suggestions>"]
    }},
    {{
      "name": "Activity & Posts",
      "score": <0 if not visible, else score>,
      "status": "<status>",
      "current": "<describe or 'Not visible'>",
      "suggestions": ["<suggestions>"]
    }}
  ],
  "quick_wins": ["<action 1>", "<action 2>", "<action 3>"],
  "advanced_tips": [
    {{"tip": "<tip>", "why": "<reason>", "how": "<how to do it>"}}
  ],
  "headline_suggestions": ["<option 1>", "<option 2>", "<option 3>"],
  "keyword_recommendations": ["<keywords>"]
}}

BEFORE RESPONDING - VERIFY:
1. Did I look at the banner area? If I see colors/images, it's NOT "missing"
2. Did I read the actual headline text?
3. Am I only marking sections as 0 if truly not visible?"""


@router.post("/analyze")
async def analyze_linkedin_screenshot(
    screenshot: UploadFile = File(...),
    context: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """Analyze a LinkedIn profile screenshot and return optimization suggestions."""
    logger.info("linkedin_analyze_start", user_id=user["id"], filename=screenshot.filename)

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

    # Use Groq vision model directly
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
        logger.info("linkedin_vision_complete", elapsed_ms=elapsed, chars=len(raw_text))
    except Exception as e:
        logger.error("linkedin_vision_failed", error=str(e))
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

    logger.info("linkedin_analyze_complete", user_id=user["id"], score=result.get("overall_score"))
    return result
