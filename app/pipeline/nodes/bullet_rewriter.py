"""
ResuMax — Node 5: STAR Bullet Rewriter
Rewrites weak bullet points using STAR format with JD keyword injection.
"""

import json
import asyncio
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

REWRITER_SYSTEM = "You are an expert resume writer specializing in STAR-format bullet points that maximize ATS scores."

REWRITE_PROMPT = """Rewrite EACH bullet point using the STAR method:
S - Situation/Context (brief)
T - Task/Challenge (what needed to be done)
A - Action (what YOU did — start with strong action verb)
R - Result (quantified outcome — use numbers, percentages, dollar amounts)

ORIGINAL BULLETS (from {company}):
{bullets}

JOB DESCRIPTION KEYWORDS TO INCORPORATE (naturally, not forced):
{relevant_keywords}

RULES:
1. Start every bullet with a STRONG ACTION VERB (Led, Architected, Engineered, Accelerated, etc.)
2. Include at least ONE metric per bullet (%, $, #, time saved, etc.)
3. If you don't know the exact metric, make a reasonable estimate marked with ~
4. Naturally incorporate JD keywords — do NOT force them
5. Keep each bullet to 1-2 lines max
6. Do NOT change the fundamental facts — only the presentation

OUTPUT (JSON):
{{
    "rewrites": [
        {{
            "original": "Managed a team of developers working on various projects",
            "rewritten": "Directed a cross-functional team of 8 engineers across 3 concurrent product initiatives, delivering all milestones ~15% ahead of schedule",
            "company": "{company}",
            "improvement_type": "star-format",
            "keywords_added": ["cross-functional", "product"],
            "confidence": 0.85,
            "reasoning": "Added team size, project count, and timeline metric. Injected 'cross-functional' from JD."
        }}
    ]
}}

Return ONLY valid JSON."""


async def bullet_rewriter_node(state: PipelineState) -> dict:
    """
    Node 5: STAR Bullet Rewriter
    Primary: bedrock_deep (Claude) | Fallback: groq_balanced (70B)
    Processes each company's bullets separately to stay within token limits.
    """
    start = time()
    logger.info("node_5_bullet_rewriter_start", analysis_id=state["analysis_id"])

    parsed = state.get("parsed_resume", {})
    experience = parsed.get("experience", [])
    keyword_matches = state.get("keyword_matches", [])

    # Get missing/important keywords to inject
    relevant_keywords = [
        k.get("keyword", "") for k in keyword_matches
        if k.get("importance") in ("critical", "important")
    ]

    primary = get_groq_balanced()
    fallback = get_groq_fast()

    all_rewrites = []

    for exp in experience:
        company = exp.get("company", "Unknown")
        bullets = exp.get("bullets", [])

        if not bullets:
            continue

        # Throttle between companies to avoid rate limits
        if all_rewrites:  # Skip delay for first company
            await asyncio.sleep(5)

        # Format bullets as numbered list
        bullet_text = "\n".join(f"{i+1}. {b}" for i, b in enumerate(bullets))

        prompt = REWRITE_PROMPT.format(
            company=company,
            bullets=bullet_text,
            relevant_keywords=json.dumps(relevant_keywords[:15]),  # Top 15 keywords
        )

        try:
            result = await call_llm_with_fallback(
                primary=primary, fallback=fallback,
                prompt=prompt, system_prompt=REWRITER_SYSTEM,
                parse_json=True,
            )
            rewrites = result.get("rewrites", [])
            # Ensure company field is set
            for rw in rewrites:
                rw["company"] = company
            all_rewrites.extend(rewrites)
        except Exception as e:
            logger.warning("bullet_rewrite_failed", company=company, error=str(e))
            continue

    elapsed = int((time() - start) * 1000)
    logger.info("node_5_bullet_rewriter_done", total_rewrites=len(all_rewrites), elapsed_ms=elapsed)

    return {
        "bullet_rewrites": all_rewrites,
        "total_bullets_rewritten": len(all_rewrites),
        "current_step": 5,
        "status": "rewriting",
        "node_timings": {**state.get("node_timings", {}), "rewrite_bullets": elapsed},
    }
