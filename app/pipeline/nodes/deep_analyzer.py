"""
ResuMax — Node 3: Deep Analyzer
Chain-of-thought holistic resume quality assessment.
"""

import json
import structlog
from time import time
from app.pipeline.state import PipelineState
from app.services.groq_client import (
    get_groq_fast,
    get_groq_balanced,
    call_llm_with_fallback,
)
from app.services.bedrock_client import get_bedrock_deep

logger = structlog.get_logger(__name__)

DEEP_SYSTEM = "You are a senior recruiter at a Fortune 500 company with 15 years of hiring experience."

DEEP_ANALYSIS_PROMPT = """You are reviewing this resume for a specific job. Think step by step:

1. EXPERIENCE LEVEL MATCH: Is this candidate junior/mid/senior? Does it match the JD?
2. INDUSTRY ALIGNMENT: How relevant is their background to this specific role/industry?
3. STRENGTHS: What makes this candidate stand out? (max 5)
4. WEAKNESSES: What would make a recruiter hesitate? (max 5)
5. GAPS: What specific competencies does the JD need that this resume doesn't demonstrate?

RESUME:
{parsed_resume}

JOB DESCRIPTION:
{job_description}

KEYWORD ANALYSIS:
{keyword_matches}

OUTPUT (JSON):
{{
    "experience_level_match": "match",
    "industry_alignment": 75,
    "strengths": ["Strong quantified achievements", "Relevant tech stack", "..."],
    "weaknesses": ["No leadership experience mentioned", "..."],
    "gap_analysis": [
        {{
            "area": "Cloud Infrastructure",
            "gap_description": "JD requires extensive AWS experience but resume shows limited cloud work",
            "suggestion": "Highlight any cloud migration or deployment experience, even from personal projects"
        }}
    ],
    "overall_assessment": "Solid mid-level candidate with strong technical skills but lacks..."
}}

RULES:
- experience_level_match must be one of: "under-qualified", "match", "over-qualified"
- industry_alignment is 0-100
- Be specific and actionable in gap suggestions
- overall_assessment should be 2-3 sentences
Return ONLY valid JSON."""


async def deep_analysis_node(state: PipelineState) -> dict:
    """
    Node 3: Deep Analysis
    Primary: bedrock_deep (Claude) | Fallback: groq_balanced (70B)
    """
    start = time()
    logger.info("node_3_deep_analysis_start", analysis_id=state["analysis_id"])

    prompt = DEEP_ANALYSIS_PROMPT.format(
        parsed_resume=json.dumps(state["parsed_resume"], indent=2),
        job_description=state["job_description"],
        keyword_matches=json.dumps(state.get("keyword_matches", []), indent=2),
    )

    primary = get_groq_balanced()
    fallback = get_groq_fast()

    result = await call_llm_with_fallback(
        primary=primary, fallback=fallback,
        prompt=prompt, system_prompt=DEEP_SYSTEM,
        parse_json=True,
    )

    elapsed = int((time() - start) * 1000)
    logger.info("node_3_deep_analysis_done", elapsed_ms=elapsed)

    return {
        "deep_analysis": result,
        "current_step": 3,
        "status": "analyzing",
        "node_timings": {**state.get("node_timings", {}), "deep_analyze": elapsed},
    }
