"""
ResuMax — Node 6: Final Optimizer
Assembles all improvements into the final optimized resume.
Generates SHRUTI suggestion cards and recalculates ATS score.
"""

import json
import uuid
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

OPTIMIZER_SYSTEM = "You are a resume optimization engine that assembles the best version of a resume from analysis data."

OPTIMIZER_PROMPT = """You have the original resume and all optimization data. Create the FINAL optimized resume.

ORIGINAL PARSED RESUME:
{parsed_resume}

BULLET REWRITES:
{bullet_rewrites}

SKILL ANALYSIS:
{skill_analysis}

KEYWORD GAPS:
{keyword_matches}

DENSITY ISSUES:
{density_analysis}

TASKS:
1. Replace original bullets with rewritten ones (matched by company + original text)
2. Add missing critical skills to skills section (from skill_analysis.missing_critical)
3. Keep all other sections unchanged (contact, education, etc.)
4. Recalculate an estimated ATS score for the optimized version (0-100)

OUTPUT (EXAMPLE JSON - DO NOT USE THESE NUMBERS, CALCULATE YOUR OWN):
{{
    "optimized_resume": {{
        "contact": {{ ... }},
        "summary": "...",
        "experience": [ ... ],
        "education": [ ... ],
        "skills": ["...(including newly added skills)..."],
        "certifications": [...],
        "projects": [...],
        "languages": [...]
    }},
    "final_ats_score": 84,
    "changes_summary": [
        "Rewrote 8 bullet points with STAR format",
        "Added 3 missing skills: Kubernetes, Terraform, CI/CD",
        "..."
    ]
}}

IMPORTANT: The `final_ats_score` of 84 is just a placeholder! You MUST estimate the true ATS score of the new optimized resume.
Return ONLY valid JSON."""


def _generate_shruti_suggestions(state: PipelineState) -> list:
    """Generate SHRUTI suggestion cards from all pipeline findings."""
    suggestions = []

    # From bullet rewrites
    for rw in state.get("bullet_rewrites", []):
        suggestions.append({
            "id": f"bullet_{uuid.uuid4().hex[:8]}",
            "category": "bullet_rewrite",
            "title": f"Rewrite bullet in {rw.get('company', 'Unknown')}",
            "description": rw.get("reasoning", "Improved bullet with STAR format"),
            "before": rw.get("original", ""),
            "after": rw.get("rewritten", ""),
            "impact": "high" if rw.get("confidence", 0) > 0.7 else "medium",
            "estimated_score_change": 3,
            "accepted": None,
        })

    # From missing skills
    skill_analysis = state.get("skill_analysis") or {}
    for skill in (skill_analysis.get("missing_critical", []) if isinstance(skill_analysis, dict) else []):
        suggestions.append({
            "id": f"skill_{uuid.uuid4().hex[:8]}",
            "category": "skill_addition",
            "title": f"Add missing skill: {skill}",
            "description": f"'{skill}' is a critical requirement in the JD but missing from your resume.",
            "before": None,
            "after": skill,
            "impact": "high",
            "estimated_score_change": 5,
            "accepted": None,
        })

    # From density issues
    density = state.get("density_analysis") or {}
    for kw in (density.get("under_represented", []) if isinstance(density, dict) else []):
        suggestions.append({
            "id": f"density_{uuid.uuid4().hex[:8]}",
            "category": "keyword_injection",
            "title": f"Increase mentions of '{kw}'",
            "description": f"'{kw}' appears too few times. Consider adding it to your experience or skills section.",
            "before": None,
            "after": None,
            "impact": "medium",
            "estimated_score_change": 2,
            "accepted": None,
        })

    # From deep analysis gaps
    deep = state.get("deep_analysis") or {}
    for gap in (deep.get("gap_analysis", []) if isinstance(deep, dict) else [])[:5]:
        suggestions.append({
            "id": f"gap_{uuid.uuid4().hex[:8]}",
            "category": "format_fix",
            "title": f"Address gap: {gap.get('area', 'Unknown')}",
            "description": gap.get("suggestion", ""),
            "before": None,
            "after": None,
            "impact": "medium",
            "estimated_score_change": 3,
            "accepted": None,
        })

    return suggestions


async def final_optimizer_node(state: PipelineState) -> dict:
    """
    Node 6: Final Optimizer
    Primary: groq_balanced (70B) | Fallback: bedrock_deep
    """
    start = time()
    logger.info("node_6_optimizer_start", analysis_id=state["analysis_id"])

    prompt = OPTIMIZER_PROMPT.format(
        parsed_resume=json.dumps(state.get("parsed_resume") or {}, indent=2),
        bullet_rewrites=json.dumps(state.get("bullet_rewrites") or [], indent=2),
        skill_analysis=json.dumps(state.get("skill_analysis") or {}, indent=2),
        keyword_matches=json.dumps(state.get("keyword_matches") or [], indent=2),
        density_analysis=json.dumps(state.get("density_analysis") or {}, indent=2),
    )

    primary = get_groq_balanced()
    fallback = get_groq_fast()

    result = await call_llm_with_fallback(
        primary=primary, fallback=fallback,
        prompt=prompt, system_prompt=OPTIMIZER_SYSTEM,
        parse_json=True,
    )

    optimized_resume = result.get("optimized_resume", state.get("parsed_resume", {}))
    final_ats_score = int(result.get("final_ats_score", state.get("ats_score", 0)))
    original_score = state.get("ats_score", 0) or 0
    score_improvement = final_ats_score - original_score

    # Generate SHRUTI suggestions from all findings
    shruti_suggestions = _generate_shruti_suggestions(state)

    elapsed = int((time() - start) * 1000)
    logger.info(
        "node_6_optimizer_done",
        original_score=original_score,
        final_score=final_ats_score,
        improvement=score_improvement,
        suggestions=len(shruti_suggestions),
        elapsed_ms=elapsed,
    )

    return {
        "optimized_resume": optimized_resume,
        "final_ats_score": final_ats_score,
        "score_improvement": score_improvement,
        "shruti_suggestions": shruti_suggestions,
        "current_step": 6,
        "status": "completed",
        "node_timings": {**state.get("node_timings", {}), "optimize_final": elapsed},
    }
