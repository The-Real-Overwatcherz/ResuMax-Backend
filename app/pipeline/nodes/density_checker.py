"""
ResuMax — Node 5b: Density Checker
Post-rewrite validation — ensures keyword density is optimal.
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

logger = structlog.get_logger(__name__)

DENSITY_SYSTEM = "You are a keyword density analysis engine for resume optimization."

DENSITY_PROMPT = """Analyze the keyword density of this optimized resume content.

OPTIMIZED RESUME BULLETS:
{optimized_text}

ORIGINAL RESUME SKILLS:
{resume_skills}

TARGET KEYWORDS (from JD):
{keywords}

For each keyword, calculate:
- Current count in the resume content
- Optimal count (2-3 for critical, 1-2 for important, 1 for nice-to-have)
- Score (100 if optimal, lower if over/under)

Also check:
- Any keyword appearing 4+ times? → Flag as "over-stuffed"
- Any critical keyword appearing 0 times? → Flag as "under-represented"
- Any formatting inconsistencies

OUTPUT (JSON):
{{
    "keyword_density_scores": [
        {{"keyword": "Python", "count": 3, "optimal_count": 3, "score": 100}},
        {{"keyword": "Kubernetes", "count": 0, "optimal_count": 2, "score": 0}}
    ],
    "overall_density_score": 72,
    "over_stuffed_keywords": ["JavaScript"],
    "under_represented": ["Kubernetes", "agile"],
    "formatting_issues": ["Inconsistent date formats between experience entries"]
}}

Return ONLY valid JSON."""


async def density_checker_node(state: PipelineState) -> dict:
    """
    Node 5b: Density Checker
    Primary: groq_fast (8B) | Fallback: bedrock_cheap or groq_balanced
    """
    start = time()
    logger.info("node_5b_density_check_start", analysis_id=state["analysis_id"])

    # Build optimized text from rewrites
    rewrites = state.get("bullet_rewrites", [])
    optimized_lines = []
    for rw in rewrites:
        optimized_lines.append(rw.get("rewritten", rw.get("original", "")))

    parsed = state.get("parsed_resume", {})
    skills = parsed.get("skills", [])

    keyword_matches = state.get("keyword_matches", [])
    keywords = [
        {"keyword": k.get("keyword", ""), "importance": k.get("importance", "important")}
        for k in keyword_matches
    ]

    prompt = DENSITY_PROMPT.format(
        optimized_text="\n".join(optimized_lines),
        resume_skills=json.dumps(skills),
        keywords=json.dumps(keywords, indent=2),
    )

    primary = get_groq_fast()
    fallback = get_bedrock_cheap() or get_groq_balanced()

    result = await call_llm_with_fallback(
        primary=primary, fallback=fallback,
        prompt=prompt, system_prompt=DENSITY_SYSTEM,
        parse_json=True,
    )

    elapsed = int((time() - start) * 1000)
    logger.info("node_5b_density_check_done", elapsed_ms=elapsed)

    return {
        "density_analysis": result,
        "current_step": 5,
        "status": "rewriting",
        "node_timings": {**state.get("node_timings", {}), "check_density": elapsed},
    }
