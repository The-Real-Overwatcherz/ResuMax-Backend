# ResuMax — Deep LangChain/LangGraph Pipeline Specification

## Overview

The ResuMax AI pipeline is built as a **LangGraph state graph** — a directed acyclic graph (DAG) of 8 specialized AI nodes, each performing a distinct analysis/transformation task. All nodes share a common `PipelineState` TypedDict and use a **dual-provider LLM strategy**: **Groq** (free tier, ultra-fast) for simple/medium tasks and **AWS Bedrock** ($200 new-account credits, Claude 3.5 Haiku) for deep reasoning tasks.

---

## Why LangGraph (Not Raw LangChain)

| Feature | LangChain LCEL | LangGraph |
|---|---|---|
| State management | Manual | Built-in TypedDict |
| Error recovery | Manual try/catch | Retry nodes, fallback edges |
| Human-in-loop | Not native | Native interrupt/resume |
| Progress tracking | Manual callbacks | Node completion events |
| Debugging | LangSmith traces | LangSmith + graph visualization |
| Cyclic flows | Not supported | Supported (JARVIS Q&A loop) |

---

## Pipeline Graph Structure

```python
from langgraph.graph import StateGraph, END

# Define the graph
graph = StateGraph(PipelineState)

# Add nodes
graph.add_node("parse_resume", parse_resume_node)
graph.add_node("ats_score", ats_scoring_node)
graph.add_node("deep_analyze", deep_analysis_node)
graph.add_node("match_skills", skill_matching_node)
graph.add_node("generate_interview", interviewer_node)
graph.add_node("rewrite_bullets", bullet_rewriter_node)
graph.add_node("check_density", density_checker_node)
graph.add_node("optimize_final", final_optimizer_node)

# Define edges (linear flow)
graph.set_entry_point("parse_resume")
graph.add_edge("parse_resume", "ats_score")
graph.add_edge("ats_score", "deep_analyze")
graph.add_edge("deep_analyze", "match_skills")
graph.add_edge("match_skills", "generate_interview")
graph.add_edge("generate_interview", "rewrite_bullets")
graph.add_edge("rewrite_bullets", "check_density")
graph.add_edge("check_density", "optimize_final")
graph.add_edge("optimize_final", END)

# Compile
pipeline = graph.compile()
```

---

## Pipeline State

```python
from typing import TypedDict, Optional, List
from pydantic import BaseModel, Field

# --- Pydantic Models for Structured Output ---

class ResumeContact(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    location: Optional[str] = None

class ExperienceEntry(BaseModel):
    company: str
    title: str
    dates: str                         # e.g. "Jan 2022 - Present"
    bullets: List[str]                 # Individual bullet points
    is_current: bool = False

class EducationEntry(BaseModel):
    institution: str
    degree: str
    field: Optional[str] = None
    dates: Optional[str] = None
    gpa: Optional[str] = None

class ParsedResume(BaseModel):
    contact: ResumeContact
    summary: Optional[str] = None
    experience: List[ExperienceEntry] = Field(default_factory=list)
    education: List[EducationEntry] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    projects: List[dict] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    raw_text: str = ""

class KeywordMatch(BaseModel):
    keyword: str
    found: bool
    location: Optional[str] = None      # "skills", "experience.bullet.3", etc.
    importance: str                      # "critical", "important", "nice-to-have"
    jd_frequency: int = 1               # How many times it appears in JD

class ATSBreakdown(BaseModel):
    keyword_score: float                 # 0-100, weight: 40%
    section_completeness: float          # 0-100, weight: 15%
    format_compliance: float             # 0-100, weight: 10%
    action_verb_usage: float             # 0-100, weight: 15%
    quantification_rate: float           # 0-100, weight: 20%
    final_score: int                     # Weighted average

class SkillAnalysis(BaseModel):
    exact_matches: List[str]             # Skills in both resume and JD
    synonym_matches: List[dict]          # e.g. {"resume": "React", "jd": "Frontend Framework"}
    implicit_skills: List[dict]          # e.g. {"skill": "Leadership", "evidence": "Led team of 5"}
    missing_critical: List[str]          # Must-have skills not in resume
    missing_optional: List[str]          # Nice-to-have skills not in resume
    recommendations: List[str]           # "Add 'Kubernetes' to your skills section"

class BulletRewrite(BaseModel):
    original: str
    rewritten: str
    company: str                          # Which company this bullet belongs to
    improvement_type: str                 # "quantified", "action-verb", "star-format", "keyword-injected"
    keywords_added: List[str]             # JD keywords injected
    confidence: float                     # 0.0 - 1.0
    reasoning: str                        # Why this change was made

class DeepAnalysis(BaseModel):
    experience_level_match: str           # "under-qualified", "match", "over-qualified"
    industry_alignment: float             # 0-100
    strengths: List[str]
    weaknesses: List[str]
    gap_analysis: List[dict]              # [{area, gap_description, suggestion}]
    overall_assessment: str               # 2-3 sentence summary

class DensityAnalysis(BaseModel):
    keyword_density_scores: List[dict]    # [{keyword, count, optimal_count, score}]
    overall_density_score: float          # 0-100
    over_stuffed_keywords: List[str]      # Keywords appearing too many times
    under_represented: List[str]          # Keywords that should appear more
    formatting_issues: List[str]          # Whitespace, consistency issues

class InterviewQuestion(BaseModel):
    question: str
    target_bullet: str                    # The bullet this question is about
    purpose: str                          # "quantification", "context", "impact", "tools"
    company: str                          # Which company entry

class JarvisSuggestion(BaseModel):
    id: str
    category: str                         # "bullet_rewrite", "keyword_injection", "skill_addition",
                                          # "section_reorder", "format_fix", "quantification"
    title: str                            # Short title for the suggestion card
    description: str                      # JARVIS's explanation
    before: Optional[str] = None
    after: Optional[str] = None
    impact: str                           # "high", "medium", "low"
    estimated_score_change: int           # e.g. +5 points
    accepted: Optional[bool] = None

# --- Main Pipeline State ---

class PipelineState(TypedDict):
    # === INPUTS ===
    resume_text: str
    resume_file_path: str
    job_description: str
    user_id: str
    analysis_id: str
    
    # === NODE 1: Parser ===
    parsed_resume: Optional[ParsedResume]
    
    # === NODE 2: ATS Scorer ===
    ats_score: Optional[int]
    ats_breakdown: Optional[ATSBreakdown]
    keyword_matches: Optional[List[KeywordMatch]]
    total_keywords_found: Optional[int]
    total_keywords_missing: Optional[int]
    
    # === NODE 3: Deep Analyzer ===
    deep_analysis: Optional[DeepAnalysis]
    
    # === NODE 3b: Skill Matcher ===
    skill_analysis: Optional[SkillAnalysis]
    
    # === NODE 4: AI Interviewer ===
    interview_questions: Optional[List[InterviewQuestion]]
    
    # === NODE 5: Bullet Rewriter ===
    bullet_rewrites: Optional[List[BulletRewrite]]
    total_bullets_rewritten: Optional[int]
    
    # === NODE 5b: Density Checker ===
    density_analysis: Optional[DensityAnalysis]
    
    # === NODE 6: Final Optimizer ===
    optimized_resume: Optional[ParsedResume]
    final_ats_score: Optional[int]
    score_improvement: Optional[int]
    
    # === JARVIS ===
    jarvis_suggestions: Optional[List[JarvisSuggestion]]
    
    # === PIPELINE META ===
    current_step: int
    status: str
    errors: List[str]
    processing_start_time: Optional[float]
    node_timings: dict  # {node_name: elapsed_ms}
```

---

## Node Specifications

### Node 1: Resume Parser (`parser.py`)

**Purpose**: Extract structured data from raw resume text using LLM with structured output.

**Input**: `resume_text` (raw string)  
**Output**: `parsed_resume` (ParsedResume model)

**Strategy**:
1. Pre-process: Clean text (remove extra whitespace, fix encoding)
2. LLM Call: Send to Groq with `response_format={"type": "json_object"}`
3. Parse: Validate against Pydantic model
4. Fallback: If parsing fails, use regex-based extraction

**Prompt Template**:
```python
PARSE_PROMPT = """You are an expert resume parser. Extract ALL information from this resume into structured JSON.

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
    "education": [...],
    "skills": ["...", "..."],
    "certifications": ["..."],
    "projects": [...],
    "languages": ["..."]
}}

RULES:
- Extract EVERY bullet point exactly as written
- Preserve all dates, numbers, and metrics
- If a field is missing, use null
- Skills should be individual items, not comma-separated strings
- Experience entries should be ordered newest first
"""
```

**LLM Config**: `temperature=0`, `max_tokens=4096`

---

### Node 2: ATS Scorer (`ats_scorer.py`)

**Purpose**: Calculate a multi-factor ATS compatibility score (0-100).

**Input**: `parsed_resume`, `job_description`  
**Output**: `ats_score`, `ats_breakdown`, `keyword_matches`

**Strategy**: Two sequential LLM calls:

**Call 1 — Extract JD Requirements**:
```python
JD_EXTRACT_PROMPT = """Analyze this job description and extract ALL requirements.

JOB DESCRIPTION:
{job_description}

OUTPUT (JSON):
{{
    "job_title": "...",
    "required_skills": [
        {{"keyword": "Python", "importance": "critical"}},
        {{"keyword": "AWS", "importance": "important"}},
        ...
    ],
    "required_experience_years": 5,
    "education_requirements": "Bachelor's in CS or related",
    "soft_skills": ["leadership", "communication"],
    "industry_keywords": ["SaaS", "enterprise", "B2B"]
}}
"""
```

**Call 2 — Score Resume Against Requirements**:
```python
ATS_SCORE_PROMPT = """You are an ATS (Applicant Tracking System) scoring engine.

Score this resume against the job requirements on these 5 factors:

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

OUTPUT (JSON):
{{
    "keyword_score": 85,
    "section_completeness": 100,
    "format_compliance": 75,
    "action_verb_usage": 60,
    "quantification_rate": 45,
    "final_score": 72,
    "keyword_matches": [
        {{"keyword": "Python", "found": true, "location": "skills", "importance": "critical"}},
        ...
    ]
}}
"""
```

---

### Node 3: Deep Analyzer (`deep_analyzer.py`)

**Purpose**: Go beyond keyword matching to assess holistic resume quality.

**Input**: `parsed_resume`, `job_description`, `keyword_matches`  
**Output**: `deep_analysis` (DeepAnalysis model)

**Chain-of-Thought Prompt**:
```python
DEEP_ANALYSIS_PROMPT = """You are a senior recruiter at a Fortune 500 company reviewing this resume.

Think step by step:

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
    "experience_level_match": "match|under-qualified|over-qualified",
    "industry_alignment": 75,
    "strengths": ["Strong quantified achievements", "Relevant tech stack", ...],
    "weaknesses": ["No leadership experience mentioned", ...],
    "gap_analysis": [
        {{
            "area": "Cloud Infrastructure",
            "gap_description": "JD requires extensive AWS experience but resume shows limited cloud work",
            "suggestion": "Highlight any cloud migration or deployment experience, even from personal projects"
        }}
    ],
    "overall_assessment": "Solid mid-level candidate with strong technical skills but lacks..."
}}
"""
```

---

### Node 3b: Semantic Skill Matcher (`skill_matcher.py`)

**Purpose**: Go beyond exact keyword matching to find semantic skill connections.

**Input**: `parsed_resume`, `job_description`  
**Output**: `skill_analysis` (SkillAnalysis model)

**Strategy**:
```python
SKILL_MATCH_PROMPT = """You are an expert at understanding the semantic relationships between skills and competencies.

Analyze the resume skills/experience against the job requirements using these categories:

1. EXACT MATCHES: Skills that appear in both resume and JD
2. SYNONYM MATCHES: Skills that are semantically equivalent
   Examples: "React" ≈ "Frontend Framework", "Scrum" ≈ "Agile", "PostgreSQL" ≈ "SQL Database"
3. IMPLICIT SKILLS: Skills demonstrated through experience but not explicitly listed
   Examples: "Led team of 8" → Leadership, "Deployed to AWS" → Cloud Computing
4. MISSING CRITICAL: Must-have skills completely absent from resume
5. MISSING OPTIONAL: Nice-to-have skills not present

RESUME SKILLS: {resume_skills}
RESUME EXPERIENCE: {resume_experience}
JOB DESCRIPTION: {job_description}

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
"""
```

---

### Node 4: AI Interviewer (`interviewer.py`)

**Purpose**: Generate targeted questions for vague/weak bullet points. These questions feed into the JARVIS interactive conversation.

**Input**: `parsed_resume`, `bullet_rewrites` (from analysis), `deep_analysis`  
**Output**: `interview_questions` (List[InterviewQuestion])

```python
INTERVIEWER_PROMPT = """You are an AI career coach preparing to interview a candidate to 
strengthen their resume. Identify bullet points that are VAGUE, UNQUANTIFIED, or PASSIVE 
and generate specific questions to extract better information.

RESUME EXPERIENCE:
{experience_entries}

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
        }},
        ...
    ]
}}

RULES:
- Only question bullets that are actually improvable
- Skip bullets that are already quantified and specific
- Maximum 10 questions total (focus on highest-impact)
"""
```

---

### Node 5: STAR Bullet Rewriter (`bullet_rewriter.py`)

**Purpose**: Rewrite every weak bullet using STAR format with JD keywords injected.

**Input**: `parsed_resume`, `keyword_matches`, `interview_questions`  
**Output**: `bullet_rewrites` (List[BulletRewrite])

```python
REWRITE_PROMPT = """You are an expert resume writer specializing in STAR-format bullet points.

Rewrite EACH bullet point below using the STAR method:
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
7. Output both original and rewritten for each bullet

OUTPUT (JSON):
{{
    "rewrites": [
        {{
            "original": "Managed a team of developers working on various projects",
            "rewritten": "Directed a cross-functional team of 8 engineers across 3 concurrent product initiatives, delivering all milestones 15% ahead of schedule",
            "company": "Acme Corp",
            "improvement_type": "star-format",
            "keywords_added": ["cross-functional", "product"],
            "confidence": 0.85,
            "reasoning": "Added team size, project count, and timeline metric. Injected 'cross-functional' from JD."
        }}
    ]
}}
"""
```

---

### Node 5b: Density Checker (`density_checker.py`)

**Purpose**: Post-rewrite validation — ensure keyword density is optimal (not too sparse, not stuffed).

**Input**: `bullet_rewrites`, `keyword_matches`, `parsed_resume`  
**Output**: `density_analysis` (DensityAnalysis)

```python
DENSITY_PROMPT = """Analyze the keyword density of this optimized resume text.

OPTIMIZED RESUME TEXT:
{optimized_text}

TARGET KEYWORDS (from JD):
{keywords}

For each keyword, calculate:
- Current count in resume
- Optimal count (2-3 for critical, 1-2 for important, 1 for nice-to-have)
- Score (100 if optimal, lower if over/under)

Also check:
- Any keyword appearing 4+ times? → Flag as "stuffed"
- Any critical keyword appearing 0 times? → Flag as "missing"
- Formatting consistency (date formats, bullet style)

OUTPUT (JSON): ...
"""
```

---

### Node 6: Final Optimizer (`optimizer.py`)

**Purpose**: Assemble all improvements into the final optimized resume. Calculate before/after ATS score.

**Input**: All previous node outputs  
**Output**: `optimized_resume`, `final_ats_score`, `score_improvement`, `jarvis_suggestions`

**Tasks**:
1. Merge all accepted bullet rewrites into resume structure
2. Add recommended missing skills to skills section
3. Suggest section reordering if beneficial
4. Generate JARVIS suggestion cards from all findings
5. Recalculate ATS score with optimized content
6. Compute score improvement delta

---

## Dual-Provider LLM Configuration

```python
from langchain_groq import ChatGroq
from langchain_aws import ChatBedrockConverse
import os

# === GROQ (Free Tier — Speed) ===

# Fast model — simple extraction tasks
groq_fast = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0,
    max_tokens=2048,
    groq_api_key=os.getenv("GROQ_API_KEY"),
)

# Balanced model — moderate reasoning
groq_balanced = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_tokens=4096,
    groq_api_key=os.getenv("GROQ_API_KEY"),
)

# === AWS BEDROCK ($200 Credits — Depth) ===

# Deep reasoning — Claude 3.5 Haiku (cheap + smart)
bedrock_deep = ChatBedrockConverse(
    model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    temperature=0,
    max_tokens=4096,
)

# Ultra-cheap fallback — Amazon Nova Micro
bedrock_cheap = ChatBedrockConverse(
    model_id="amazon.nova-micro-v1:0",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    temperature=0,
    max_tokens=2048,
)

# Model assignment per node (primary → fallback):
# Node 1 (Parser):          groq_fast (8B)        → bedrock_cheap   — simple extraction
# Node 2 (ATS Scorer):      groq_balanced (70B)   → bedrock_deep    — keyword reasoning
# Node 3 (Deep Analyzer):   bedrock_deep (Claude)  → groq_balanced   — complex CoT reasoning
# Node 3b (Skill Matcher):  groq_balanced (70B)   → bedrock_deep    — semantic matching
# Node 4 (Interviewer):     bedrock_deep (Claude)  → groq_balanced   — nuanced questions
# Node 5 (Bullet Rewriter): bedrock_deep (Claude)  → groq_balanced   — creative writing
# Node 5b (Density Check):  groq_fast (8B)        → bedrock_cheap   — counting/validation
# Node 6 (Optimizer):       groq_balanced (70B)   → bedrock_deep    — final assembly
# JARVIS:                   bedrock_deep (Claude)  → groq_balanced   — personality + wit

# Per-analysis cost: ~$0.015 Bedrock + $0.00 Groq = ~$0.015 total
# Capacity: ~13,300 analyses from $200 Bedrock credits
# Groq daily: ~125 complete analyses/day (1000 RPD ÷ 8 calls)
```

---

## Error Handling & Provider Fallback Strategy

```python
from tenacity import retry, stop_after_attempt, wait_exponential

# Each node is wrapped with error handling + provider fallback:
async def safe_node(state: PipelineState, node_fn, node_name: str,
                    primary_llm, fallback_llm) -> PipelineState:
    try:
        state["status"] = node_name
        result = await node_fn(state, llm=primary_llm)
        state["node_timings"][node_name] = elapsed_ms
        state["models_used"][node_name] = primary_llm.model_id
        return result
    except Exception as primary_err:
        # Log primary failure and try fallback provider
        state["errors"].append(f"{node_name} primary failed: {str(primary_err)}")
        try:
            result = await node_fn(state, llm=fallback_llm)
            state["models_used"][node_name] = f"{fallback_llm.model_id} (fallback)"
            return result
        except Exception as fallback_err:
            state["errors"].append(f"{node_name} fallback failed: {str(fallback_err)}")
            state["status"] = "failed"
            # Still return state so pipeline can continue with partial results
            return state
```

---

## Rate Limiting Strategy

```python
# Groq free tier: 30 RPM for 70B model
# Our pipeline makes ~8 calls per analysis
# Max throughput: ~3.75 analyses per minute

import asyncio
from collections import deque
from time import time

class RateLimiter:
    def __init__(self, rpm: int = 25):  # Leave 5 RPM headroom
        self.rpm = rpm
        self.timestamps = deque()
    
    async def acquire(self):
        now = time()
        # Remove timestamps older than 60 seconds
        while self.timestamps and self.timestamps[0] < now - 60:
            self.timestamps.popleft()
        
        if len(self.timestamps) >= self.rpm:
            sleep_time = 60 - (now - self.timestamps[0])
            await asyncio.sleep(sleep_time)
        
        self.timestamps.append(time())
```
