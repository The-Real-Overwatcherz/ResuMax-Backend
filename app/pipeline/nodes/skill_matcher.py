"""
ResuMax — Node 3b: Semantic Skill Matcher
Goes beyond exact keyword matching to find semantic skill connections.
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

SKILL_SYSTEM = "You are an expert at understanding the semantic relationships between skills, technologies, and competencies."

SKILL_MATCH_PROMPT = """Analyze the resume skills/experience against the job requirements using these categories:

1. EXACT MATCHES: Skills that appear in both resume and JD
2. SYNONYM MATCHES: Skills that are semantically equivalent
   Examples: "React" ≈ "Frontend Framework", "Scrum" ≈ "Agile", "PostgreSQL" ≈ "SQL Database"
3. IMPLICIT SKILLS: Skills demonstrated through experience but not explicitly listed
   Examples: "Led team of 8" → Leadership, "Deployed to AWS" → Cloud Computing
4. MISSING CRITICAL: Must-have skills completely absent from resume
5. MISSING OPTIONAL: Nice-to-have skills not present

RESUME SKILLS: {resume_skills}

RESUME EXPERIENCE:
{resume_experience}

JOB DESCRIPTION:
{job_description}

OUTPUT (JSON):
{{
    "exact_matches": ["Python", "Docker", "React"],
    "synonym_matches": [
        {{"resume": "PostgreSQL", "jd": "SQL databases"}},
        {{"resume": "Jest", "jd": "Unit Testing"}}
    ],
    "implicit_skills": [
        {{"skill": "Project Management", "evidence": "Led cross-functional team of 12..."}},
        {{"skill": "CI/CD", "evidence": "Deployed microservices using Docker containers..."}}
    ],
    "missing_critical": ["Kubernetes", "Terraform"],
    "missing_optional": ["GraphQL", "Redis"],
    "recommendations": [
        "Add 'Kubernetes' to your skills section — it's mentioned 4 times in the JD",
        "Your Docker experience implies container orchestration — mention K8s even if limited"
    ]
}}

Return ONLY valid JSON."""


async def skill_matching_node(state: PipelineState) -> dict:
    """
    Node 3b: Semantic Skill Matcher
    Primary: groq_balanced (70B) | Fallback: bedrock_deep
    """
    start = time()
    logger.info("node_3b_skill_match_start", analysis_id=state["analysis_id"])

    parsed = state.get("parsed_resume", {})
    skills = parsed.get("skills", [])
    experience = parsed.get("experience", [])

    # Format experience for prompt
    exp_text = ""
    for exp in experience:
        exp_text += f"\n{exp.get('title', '')} at {exp.get('company', '')} ({exp.get('dates', '')})\n"
        for bullet in exp.get("bullets", []):
            exp_text += f"  • {bullet}\n"

    prompt = SKILL_MATCH_PROMPT.format(
        resume_skills=json.dumps(skills),
        resume_experience=exp_text,
        job_description=state["job_description"],
    )

    primary = get_groq_balanced()
    fallback = get_groq_fast()

    result = await call_llm_with_fallback(
        primary=primary, fallback=fallback,
        prompt=prompt, system_prompt=SKILL_SYSTEM,
        parse_json=True,
    )

    elapsed = int((time() - start) * 1000)
    logger.info("node_3b_skill_match_done", elapsed_ms=elapsed)

    return {
        "skill_analysis": result,
        "current_step": 3,
        "status": "analyzing",
        "node_timings": {**state.get("node_timings", {}), "match_skills": elapsed},
    }
