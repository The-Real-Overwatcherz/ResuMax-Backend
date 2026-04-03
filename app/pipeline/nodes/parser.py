"""
ResuMax — Node 1: Resume Parser
Extracts structured data from raw resume text using LLM.
"""

import json
import structlog
from time import time
from app.pipeline.state import PipelineState
from app.services.groq_client import (
    get_groq_fast, get_groq_balanced,
    call_llm_with_fallback,
)
from app.services.bedrock_client import get_bedrock_cheap
from app.models.resume import ParsedResume

logger = structlog.get_logger(__name__)

PARSE_SYSTEM = "You are an expert resume parser. You extract structured data from resumes with perfect accuracy."

PARSE_PROMPT = """Extract ALL information from this resume into structured JSON.

RESUME TEXT:
{resume_text}

OUTPUT FORMAT (JSON):
{{
    "contact": {{
        "full_name": "...",
        "email": "...",
        "phone": "...",
        "linkedin": "...",
        "location": "..."
    }},
    "summary": "...",
    "experience": [
        {{
            "company": "...",
            "title": "...",
            "dates": "...",
            "bullets": ["...", "..."],
            "is_current": false
        }}
    ],
    "education": [
        {{
            "institution": "...",
            "degree": "...",
            "field": "...",
            "dates": "...",
            "gpa": null
        }}
    ],
    "skills": ["...", "..."],
    "certifications": ["..."],
    "projects": [{{"name": "...", "description": "...", "technologies": ["..."]}}],
    "languages": ["..."]
}}

RULES:
- Extract EVERY bullet point exactly as written
- Preserve all dates, numbers, and metrics
- If a field is missing, use null
- Skills should be individual items, not comma-separated strings
- Experience entries should be ordered newest first
- Return ONLY valid JSON, no extra text"""


async def parse_resume_node(state: PipelineState) -> dict:
    """
    Node 1: Parse raw resume text into structured ParsedResume.
    Primary: groq_fast (8B) | Fallback: bedrock_cheap or groq_balanced
    """
    start = time()
    logger.info("node_1_parse_resume_start", analysis_id=state["analysis_id"])

    resume_text = state["resume_text"]

    # Truncate if too long (LLM context limits)
    if len(resume_text) > 15000:
        resume_text = resume_text[:15000]
        logger.warning("resume_text_truncated", original_len=len(state["resume_text"]))

    prompt = PARSE_PROMPT.format(resume_text=resume_text)

    primary = get_groq_fast()
    fallback = get_bedrock_cheap() or get_groq_balanced()

    result = await call_llm_with_fallback(
        primary=primary,
        fallback=fallback,
        prompt=prompt,
        system_prompt=PARSE_SYSTEM,
        parse_json=True,
    )

    # Validate with Pydantic
    try:
        parsed = ParsedResume(**result)
        parsed.raw_text = state["resume_text"]
        parsed_dict = parsed.model_dump()
    except Exception as e:
        logger.warning("pydantic_validation_partial", error=str(e))
        # Use raw dict with defaults
        parsed_dict = result
        parsed_dict["raw_text"] = state["resume_text"]

    elapsed = int((time() - start) * 1000)
    logger.info("node_1_parse_resume_done", elapsed_ms=elapsed)

    return {
        "parsed_resume": parsed_dict,
        "current_step": 1,
        "status": "parsing",
        "node_timings": {**state.get("node_timings", {}), "parse_resume": elapsed},
    }
