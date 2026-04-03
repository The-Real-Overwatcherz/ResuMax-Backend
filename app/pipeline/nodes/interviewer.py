"""
ResuMax — Node 4: AI Interviewer
Generates targeted questions for vague/weak bullet points.
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

INTERVIEWER_SYSTEM = "You are an AI career coach preparing to interview a candidate to strengthen their resume."

INTERVIEWER_PROMPT = """Identify bullet points that are VAGUE, UNQUANTIFIED, or PASSIVE and generate specific questions to extract better information.

RESUME EXPERIENCE:
{experience_entries}

DEEP ANALYSIS (weaknesses to target):
{weaknesses}

For each weak bullet, generate 1-2 targeted questions.

QUESTION TYPES:
- QUANTIFICATION: "How many users/customers/team members were involved?"
- CONTEXT: "What was the business challenge you were solving?"
- IMPACT: "What measurable result did this produce?"
- TOOLS: "What specific technologies/tools did you use?"

OUTPUT (JSON):
{{
    "questions": [
        {{
            "question": "You mentioned 'managed the development team' — how many engineers, and what was the project outcome?",
            "target_bullet": "Managed the development team for multiple projects",
            "purpose": "quantification",
            "company": "Acme Corp"
        }}
    ]
}}

RULES:
- Only question bullets that are actually improvable
- Skip bullets that are already quantified and specific
- Maximum 10 questions total (focus on highest-impact)
- purpose must be one of: "quantification", "context", "impact", "tools"
Return ONLY valid JSON."""


async def interviewer_node(state: PipelineState) -> dict:
    """
    Node 4: AI Interviewer
    Primary: bedrock_deep (Claude) | Fallback: groq_balanced (70B)
    """
    start = time()
    logger.info("node_4_interviewer_start", analysis_id=state["analysis_id"])

    parsed = state.get("parsed_resume", {})
    experience = parsed.get("experience", [])

    # Format experience entries
    exp_text = ""
    for exp in experience:
        exp_text += f"\n### {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('dates', '')})\n"
        for bullet in exp.get("bullets", []):
            exp_text += f"  • {bullet}\n"

    # Get weaknesses from deep analysis (null-safe if upstream node failed)
    deep = state.get("deep_analysis") or {}
    weaknesses = deep.get("weaknesses", []) if isinstance(deep, dict) else []

    prompt = INTERVIEWER_PROMPT.format(
        experience_entries=exp_text,
        weaknesses=json.dumps(weaknesses, indent=2),
    )

    primary = get_groq_balanced()
    fallback = get_groq_fast()

    result = await call_llm_with_fallback(
        primary=primary, fallback=fallback,
        prompt=prompt, system_prompt=INTERVIEWER_SYSTEM,
        parse_json=True,
    )

    questions = result.get("questions", [])

    elapsed = int((time() - start) * 1000)
    logger.info("node_4_interviewer_done", questions=len(questions), elapsed_ms=elapsed)

    return {
        "interview_questions": questions,
        "current_step": 4,
        "status": "interviewing",
        "node_timings": {**state.get("node_timings", {}), "generate_interview": elapsed},
    }
