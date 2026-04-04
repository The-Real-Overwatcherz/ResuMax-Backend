"""
ResuMax — Node 2: ATS Scorer
Calculates multi-factor ATS compatibility score (0-100).
Two sequential LLM calls: extract JD requirements → score resume.
"""

import json
import structlog
from time import time
from app.pipeline.state import PipelineState
from app.services.groq_client import (
    get_groq_balanced, get_groq_fast,
    call_llm_with_fallback,
)
from app.services.bedrock_client import get_bedrock_deep

logger = structlog.get_logger(__name__)

# ── Prompt: Extract JD Requirements ──────────────────────────────

JD_SYSTEM = "You are an expert at analyzing job descriptions and extracting structured requirements."

JD_EXTRACT_PROMPT = """Analyze this job description and extract ALL requirements.

JOB DESCRIPTION:
{job_description}

OUTPUT (JSON):
{{
    "job_title": "...",
    "required_skills": [
        {{"keyword": "Python", "importance": "critical"}},
        {{"keyword": "AWS", "importance": "important"}},
        {{"keyword": "GraphQL", "importance": "nice-to-have"}}
    ],
    "required_experience_years": 5,
    "education_requirements": "Bachelor's in CS or related",
    "soft_skills": ["leadership", "communication"],
    "industry_keywords": ["SaaS", "enterprise", "B2B"]
}}

IMPORTANCE LEVELS:
- "critical": appears multiple times, in title, or listed as "required"
- "important": mentioned clearly but not emphasized
- "nice-to-have": listed as "preferred", "bonus", or mentioned once

Return ONLY valid JSON."""

# ── Prompt: Score Resume ─────────────────────────────────────────

ATS_SYSTEM = "You are an ATS (Applicant Tracking System) scoring engine with deep expertise in resume evaluation."

ATS_SCORE_PROMPT = """Score this resume against the job requirements on 5 factors.

RESUME DATA:
{parsed_resume}

JOB REQUIREMENTS:
{jd_requirements}

SCORING RUBRIC:
1. KEYWORD_SCORE (40% weight): What percentage of required keywords appear in resume?
   - Check exact matches AND reasonable synonyms
   - Weight "critical" keywords 3x, "important" 2x, "nice-to-have" 1x

2. SECTION_COMPLETENESS (15% weight): Does resume have all standard sections?
   - Required: Contact, Experience, Education, Skills (25% each)
   - Bonus: Summary, Certifications, Projects

3. FORMAT_COMPLIANCE (10% weight): Is the resume ATS-parseable?
   - Standard section headers? (+25)
   - Consistent date format? (+25)
   - Bullet points (not paragraphs)? (+25)
   - No tables/columns/graphics? (+25)

4. ACTION_VERB_USAGE (15% weight): % of bullets starting with strong action verbs
   - "Led", "Developed", "Increased" = strong
   - "Responsible for", "Helped with" = weak

5. QUANTIFICATION_RATE (20% weight): % of bullets with measurable metrics
   - Numbers, percentages, dollar amounts, time periods

OUTPUT (EXAMPLE JSON - YOU MUST CALCULATE YOUR OWN ACCURATE NUMBERS):
{{
    "keyword_score": 85,
    "section_completeness": 100,
    "format_compliance": 75,
    "action_verb_usage": 60,
    "quantification_rate": 45,
    "final_score": 72,
    "keyword_matches": [
        {{"keyword": "Python", "found": true, "location": "skills", "importance": "critical", "jd_frequency": 3}},
        {{"keyword": "Kubernetes", "found": false, "location": null, "importance": "critical", "jd_frequency": 2}}
    ]
}}

IMPORTANT: The numbers in the example are just placeholders. DO NOT copy them.
final_score must be the weighted average: keyword*0.4 + section*0.15 + format*0.1 + verbs*0.15 + quant*0.2
Return ONLY valid JSON. Return no preamble and no explanations."""


async def ats_scoring_node(state: PipelineState) -> dict:
    """
    Node 2: ATS Scorer
    Primary: groq_balanced (70B) | Fallback: bedrock_deep or groq_fast
    """
    start = time()
    logger.info("node_2_ats_score_start", analysis_id=state["analysis_id"])

    parsed_resume = json.dumps(state["parsed_resume"], indent=2)
    job_description = state["job_description"]

    primary = get_groq_balanced()
    fallback = get_bedrock_deep() or get_groq_fast()

    # ── Call 1: Extract JD Requirements ──
    jd_prompt = JD_EXTRACT_PROMPT.format(job_description=job_description)
    jd_requirements = await call_llm_with_fallback(
        primary=primary, fallback=fallback,
        prompt=jd_prompt, system_prompt=JD_SYSTEM,
        parse_json=True,
    )

    extracted_title = jd_requirements.get("job_title") if jd_requirements else None
    if extracted_title:
        try:
            from app.services.supabase import update_analysis_status
            await update_analysis_status(state["analysis_id"], status="scoring", step=2, job_title=extracted_title)
        except Exception:
            pass

    # ── Call 2: Score Resume ──
    ats_prompt = ATS_SCORE_PROMPT.format(
        parsed_resume=parsed_resume,
        jd_requirements=json.dumps(jd_requirements, indent=2),
    )
    ats_result = await call_llm_with_fallback(
        primary=primary, fallback=fallback,
        prompt=ats_prompt, system_prompt=ATS_SYSTEM,
        parse_json=True,
    )

    # Extract fields with defaults
    keyword_matches = ats_result.get("keyword_matches", [])
    found = sum(1 for k in keyword_matches if k.get("found", False))
    missing = sum(1 for k in keyword_matches if not k.get("found", False))

    elapsed = int((time() - start) * 1000)
    logger.info("node_2_ats_score_done", score=ats_result.get("final_score"), elapsed_ms=elapsed)

    return {
        "ats_score": int(ats_result.get("final_score", 0)),
        "ats_breakdown": {
            "keyword_score": ats_result.get("keyword_score", 0),
            "section_completeness": ats_result.get("section_completeness", 0),
            "format_compliance": ats_result.get("format_compliance", 0),
            "action_verb_usage": ats_result.get("action_verb_usage", 0),
            "quantification_rate": ats_result.get("quantification_rate", 0),
            "final_score": int(ats_result.get("final_score", 0)),
        },
        "keyword_matches": keyword_matches,
        "total_keywords_found": found,
        "total_keywords_missing": missing,
        "job_title": extracted_title,
        "current_step": 2,
        "status": "scoring",
        "node_timings": {**state.get("node_timings", {}), "ats_score": elapsed},
    }
