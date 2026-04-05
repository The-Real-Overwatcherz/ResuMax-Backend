"""
ResuMax Backend — Cold Outreach Generator API
Generate personalized LinkedIn requests, cold emails, and follow-ups.
"""

import structlog
from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user
from app.services.file_parser import parse_resume_file
from app.services.groq_client import get_groq_balanced, get_groq_fast, call_llm_with_fallback
from app.services.behavior_profiler import get_or_analyze_profile, build_adaptive_prompt

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/cold-outreach", tags=["cold-outreach"])


class OutreachRequest(BaseModel):
    resume_text: str
    target_company: str
    target_role: str = ""
    target_person: str = ""
    target_person_title: str = ""
    context: str = ""


SYSTEM_PROMPT = """You are Shruti, ResuMax's AI Career Strategist. You specialize in crafting high-converting cold outreach messages that feel personal and genuine — never spammy.

You MUST return a valid JSON object with this exact structure:
{
  "linkedin_connection": {
    "message": "The LinkedIn connection request (under 300 chars)",
    "note": "Why this approach works"
  },
  "cold_email": {
    "subject": "Email subject line",
    "body": "Full email body (3-5 short paragraphs)",
    "note": "Why this approach works"
  },
  "follow_up": {
    "message": "Follow-up message if no response after 5-7 days",
    "note": "Why this approach works"
  },
  "linkedin_comment": {
    "example": "A thoughtful comment to leave on their recent post to get on their radar first",
    "note": "Strategy behind this"
  },
  "strategy_tips": [
    "Tip 1 for maximizing response rate",
    "Tip 2",
    "Tip 3"
  ]
}

Rules:
- Reference specific skills/experience from the resume that are relevant to the target company/role
- Never be generic — every message must feel custom-written
- Keep LinkedIn request under 300 characters
- Cold email should be concise (under 150 words), no fluff
- Include a specific ask or CTA in each message
- Follow-up should add new value, not just "checking in"
- Return ONLY the JSON, no markdown fences"""


@router.post("/generate")
async def generate_outreach(
    request: OutreachRequest,
    user: dict = Depends(get_current_user),
):
    """Generate personalized cold outreach messages."""
    logger.info("cold_outreach_generate", user_id=user["id"], company=request.target_company)

    # Behavioral adaptation
    adaptive_prompt = build_adaptive_prompt(SYSTEM_PROMPT,
        await get_or_analyze_profile(user["id"], [{"role": "user", "content": request.context or request.target_company}])
    )

    person_context = ""
    if request.target_person:
        person_context = f"\nTarget Person: {request.target_person}"
        if request.target_person_title:
            person_context += f" ({request.target_person_title})"

    prompt = f"""CANDIDATE'S RESUME:
{request.resume_text[:4000]}

TARGET COMPANY: {request.target_company}
TARGET ROLE: {request.target_role or "Not specified — infer from resume"}
{person_context}
{f"ADDITIONAL CONTEXT: {request.context}" if request.context else ""}

Generate personalized outreach messages. Make them specific to this person's actual experience and the target company. Return the JSON."""

    result = await call_llm_with_fallback(
        primary=get_groq_balanced(),
        fallback=get_groq_fast(),
        prompt=prompt,
        system_prompt=adaptive_prompt,
        parse_json=True,
    )

    return result


@router.post("/generate-with-file")
async def generate_outreach_with_file(
    resume: UploadFile = File(...),
    target_company: str = Form(...),
    target_role: str = Form(""),
    target_person: str = Form(""),
    target_person_title: str = Form(""),
    context: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """Generate outreach from an uploaded resume file."""
    file_bytes = await resume.read()
    resume_text = parse_resume_file(file_bytes, resume.filename or "upload.pdf")

    request = OutreachRequest(
        resume_text=resume_text,
        target_company=target_company,
        target_role=target_role,
        target_person=target_person,
        target_person_title=target_person_title,
        context=context,
    )
    return await generate_outreach(request, user)
