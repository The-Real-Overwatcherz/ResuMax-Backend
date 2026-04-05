"""
ResuMax — Behavioral AI Profiler Service
Uses Ollama Cloud (qwen3.5:9b) to analyze user communication patterns
and adapt SHRUTI's responses to match each user's behavioral style.

Architecture:
    User messages → qwen3.5 (profile behavior) → traits injected into system prompt → Groq (generate response)
"""

import json
import re
import asyncio
import structlog
import httpx
from typing import Optional
from time import time
from collections import deque

from app.config import get_settings

logger = structlog.get_logger(__name__)


# ── Behavior Trait Definitions ──────────────────────────────────

BEHAVIOR_DIMENSIONS = {
    "confidence": {
        "low": "User seems uncertain, hesitant, uses hedging language (maybe, I think, not sure). Be extra encouraging, validate their strengths, break advice into small steps.",
        "medium": "User is moderately confident. Balance encouragement with honest feedback.",
        "high": "User is self-assured and direct. Skip excessive encouragement, be direct and specific with advanced tips.",
    },
    "communication_style": {
        "brief": "User sends short, terse messages. Match their brevity — give concise, punchy responses. No fluff.",
        "conversational": "User is chatty and casual. Be warm, use a friendly tone, add personality.",
        "detailed": "User writes long, detailed messages. Give thorough, structured responses with specifics.",
    },
    "experience_level": {
        "beginner": "User appears new to job searching or resume writing. Explain concepts, avoid jargon, be patient and supportive.",
        "intermediate": "User has some experience. Give practical tips without over-explaining basics.",
        "expert": "User clearly knows the domain well. Use industry terminology, focus on advanced optimization strategies.",
    },
    "emotional_state": {
        "anxious": "User seems stressed or worried about their career/job search. Be calming, reassuring, and empathetic. Acknowledge their feelings before giving advice.",
        "neutral": "User is calm and matter-of-fact. Respond professionally and efficiently.",
        "enthusiastic": "User is excited and motivated. Match their energy, encourage their momentum, suggest ambitious improvements.",
        "frustrated": "User seems frustrated or discouraged. Be patient, acknowledge the difficulty, focus on quick wins to rebuild confidence.",
    },
    "learning_preference": {
        "examples": "User responds well to examples and concrete samples. Include before/after examples, sample bullets, template phrases.",
        "explanations": "User wants to understand the 'why'. Explain reasoning behind suggestions — why ATS works this way, why this phrasing is better.",
        "action_items": "User wants clear next steps. Give numbered action items, checklists, and direct instructions.",
    },
}


# ── Ollama Cloud Client ─────────────────────────────────────────

_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    """Get or create the HTTP client for Ollama Cloud."""
    global _http_client
    if _http_client is None:
        settings = get_settings()
        _http_client = httpx.AsyncClient(
            base_url=settings.ollama_cloud_base_url,
            headers={
                "Authorization": f"Bearer {settings.ollama_cloud_api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        logger.info("ollama_cloud_client_initialized", base_url=settings.ollama_cloud_base_url)
    return _http_client


async def _call_ollama_cloud(system_prompt: str, user_prompt: str) -> str:
    """
    Call Ollama Cloud API at https://ollama.com/api/chat.
    Uses Ollama's native chat format (not OpenAI-compatible).
    Docs: https://docs.ollama.com/cloud
    """
    settings = get_settings()
    client = _get_http_client()

    payload = {
        "model": settings.ollama_cloud_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 2048,
        },
    }

    start = time()
    try:
        response = await client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        elapsed = int((time() - start) * 1000)

        # Qwen 3.5 uses a thinking field — content may be empty
        content = data["message"].get("content", "").strip()
        thinking = data["message"].get("thinking", "").strip()

        logger.info(
            "ollama_cloud_call",
            model=settings.ollama_cloud_model,
            elapsed_ms=elapsed,
            content_len=len(content),
            thinking_len=len(thinking),
        )

        # Return content if available, otherwise return thinking for parsing
        return content if content else thinking
    except Exception as e:
        logger.error("ollama_cloud_error", error=str(e), status=getattr(e, 'response', None))
        raise


# ── Behavior Analysis ───────────────────────────────────────────

PROFILER_SYSTEM_PROMPT = """You are a behavioral analysis engine. Your job is to analyze a user's messages and determine their behavioral profile across 5 dimensions.

Analyze the user's messages and return a JSON object with EXACTLY these keys:
{
  "confidence": "low" | "medium" | "high",
  "communication_style": "brief" | "conversational" | "detailed",
  "experience_level": "beginner" | "intermediate" | "expert",
  "emotional_state": "anxious" | "neutral" | "enthusiastic" | "frustrated",
  "learning_preference": "examples" | "explanations" | "action_items"
}

Rules:
- Base your analysis ONLY on the messages provided
- Look at word choice, sentence length, tone, vocabulary, punctuation, and content
- If uncertain, default to: medium confidence, conversational, intermediate, neutral, explanations
- Return ONLY the JSON object, no other text
- Do NOT wrap in markdown code fences"""


async def analyze_behavior(messages: list[dict]) -> dict:
    """
    Analyze user messages to build a behavioral profile.

    Args:
        messages: List of {"role": "user"/"assistant", "content": "..."} dicts

    Returns:
        Dict with 5 behavior dimensions
    """
    # Extract only user messages for analysis
    user_messages = [m["content"] for m in messages if m.get("role") == "user"]

    if not user_messages:
        return _default_profile()

    # Use last 8 user messages max for analysis
    recent = user_messages[-8:]
    messages_text = "\n---\n".join(f"Message {i+1}: {msg}" for i, msg in enumerate(recent))

    user_prompt = f"""Analyze these user messages and determine their behavioral profile:

{messages_text}

Return the JSON behavioral profile."""

    try:
        raw = await _call_ollama_cloud(PROFILER_SYSTEM_PROMPT, user_prompt)
        profile = _parse_profile_response(raw)

        logger.info("behavior_profile_analyzed", profile=profile)
        return profile

    except Exception as e:
        logger.warning("behavior_analysis_failed", error=str(e))
        return _default_profile()


def _parse_profile_response(raw: str) -> dict:
    """
    Parse behavior profile from LLM response.
    Handles 3 cases:
      1. Clean JSON output (most models)
      2. JSON inside thinking tags or markdown fences
      3. Qwen 3.5 thinking text where values are mentioned but no clean JSON
    """
    text = raw.strip()

    # Strip thinking tags
    if "<think>" in text:
        think_end = text.find("</think>")
        if think_end != -1:
            after_think = text[think_end + 8:].strip()
            if after_think:
                text = after_think

    # Strip markdown fences
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Strategy 1: Try to find and parse a complete JSON object
    json_matches = list(re.finditer(r'\{[^{}]*\}', text))
    for match in json_matches:
        try:
            candidate = json.loads(match.group())
            # Check if it has at least 3 of our expected keys
            expected_keys = {"confidence", "communication_style", "experience_level", "emotional_state", "learning_preference"}
            if len(expected_keys & set(candidate.keys())) >= 3:
                return _validate_profile(candidate)
        except json.JSONDecodeError:
            continue

    # Strategy 2: Extract values from thinking text using regex
    # Qwen 3.5 writes things like: `confidence`: `low`, Selection: `low`, I'll pick `frustrated`
    extracted = {}
    for dim, options in BEHAVIOR_DIMENSIONS.items():
        for value in options.keys():
            # Match patterns like: "confidence": "low" or confidence: low or Selection: `low`
            patterns = [
                rf'"{dim}":\s*"{value}"',           # "confidence": "low"
                rf"`{dim}`:\s*`{value}`",            # `confidence`: `low`
                rf'{dim}.*?:\s*`?{value}`?',         # confidence: low or confidence: `low`
                rf"Selection:\s*`?{value}`?",        # Selection: `low` (near the dimension context)
                rf"I'll (?:pick|go with|select|choose|use)\s*`?{value}`?",  # I'll pick frustrated
            ]
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # For generic patterns (Selection/I'll pick), verify it's near the right dimension
                    if "Selection" in pattern or "I'll" in pattern:
                        # Find the match position and check if dimension name is nearby (within 500 chars before)
                        m = re.search(pattern, text, re.IGNORECASE)
                        if m:
                            context_before = text[max(0, m.start() - 500):m.start()]
                            if dim in context_before or dim.replace("_", " ") in context_before:
                                extracted[dim] = value
                                break
                    else:
                        extracted[dim] = value
                        break

    if len(extracted) >= 3:
        return _validate_profile(extracted)

    # Strategy 3: Last resort — look for the last mention of each valid value
    for dim, options in BEHAVIOR_DIMENSIONS.items():
        if dim not in extracted:
            # Find which value appears last in the text (most likely the final decision)
            last_pos = -1
            last_val = None
            for value in options.keys():
                pos = text.rfind(value)
                if pos > last_pos:
                    last_pos = pos
                    last_val = value
            if last_val:
                extracted[dim] = last_val

    if extracted:
        return _validate_profile(extracted)

    return _default_profile()


def _validate_profile(profile: dict) -> dict:
    """Ensure all dimensions exist with valid values."""
    validated = {}
    for dim, options in BEHAVIOR_DIMENSIONS.items():
        val = profile.get(dim, "")
        validated[dim] = val if val in options else list(options.keys())[1]  # default to middle
    return validated


def _default_profile() -> dict:
    """Return the default (neutral) behavioral profile."""
    return {
        "confidence": "medium",
        "communication_style": "conversational",
        "experience_level": "intermediate",
        "emotional_state": "neutral",
        "learning_preference": "explanations",
    }


# ── Adaptive Prompt Builder ─────────────────────────────────────

def build_adaptive_prompt(base_system_prompt: str, behavior_profile: dict) -> str:
    """
    Inject behavioral adaptation instructions into the system prompt.

    Takes the existing SHRUTI system prompt and appends behavior-specific
    instructions based on the user's detected profile.
    """
    if not behavior_profile:
        return base_system_prompt

    # Build behavior instructions
    instructions = []
    for dimension, value in behavior_profile.items():
        if dimension in BEHAVIOR_DIMENSIONS and value in BEHAVIOR_DIMENSIONS[dimension]:
            instructions.append(BEHAVIOR_DIMENSIONS[dimension][value])

    if not instructions:
        return base_system_prompt

    behavior_block = "\n".join(f"- {inst}" for inst in instructions)

    adaptive_prompt = f"""{base_system_prompt}

BEHAVIORAL ADAPTATION — Adapt your responses based on this user's communication style:
{behavior_block}

Important: Apply these adaptations naturally. Do NOT mention that you're adapting your style or reference this profiling. Just naturally match the user's energy and needs."""

    return adaptive_prompt


# ── In-Memory Profile Cache ─────────────────────────────────────
# Cache profiles per user to avoid re-analyzing every message.
# Re-analyze every 5 messages or after 10 minutes.

_profile_cache: dict[str, dict] = {}  # user_id -> {"profile": {...}, "msg_count": int, "timestamp": float}

REANALYZE_AFTER_MESSAGES = 5
REANALYZE_AFTER_SECONDS = 600  # 10 minutes


async def get_or_analyze_profile(user_id: str, messages: list[dict]) -> dict:
    """
    Get cached profile or analyze fresh if stale.
    Re-analyzes after every 5 user messages or 10 minutes.
    """
    now = time()
    user_msg_count = sum(1 for m in messages if m.get("role") == "user")

    cached = _profile_cache.get(user_id)

    if cached:
        msgs_since = user_msg_count - cached["msg_count"]
        time_since = now - cached["timestamp"]

        if msgs_since < REANALYZE_AFTER_MESSAGES and time_since < REANALYZE_AFTER_SECONDS:
            return cached["profile"]

    # Analyze fresh
    profile = await analyze_behavior(messages)

    _profile_cache[user_id] = {
        "profile": profile,
        "msg_count": user_msg_count,
        "timestamp": now,
    }

    return profile


# ── Supabase Persistence ────────────────────────────────────────

async def save_profile_to_db(user_id: str, profile: dict) -> None:
    """Persist behavior profile to Supabase for cross-session continuity."""
    try:
        from app.services.supabase import get_supabase_client
        client = get_supabase_client()
        client.table("behavior_profiles").upsert({
            "user_id": user_id,
            "profile": profile,
        }).execute()
        logger.info("behavior_profile_saved", user_id=user_id)
    except Exception as e:
        logger.warning("behavior_profile_save_failed", error=str(e))


async def load_profile_from_db(user_id: str) -> dict | None:
    """Load a previously saved behavior profile from Supabase."""
    try:
        from app.services.supabase import get_supabase_client
        client = get_supabase_client()
        result = client.table("behavior_profiles").select("profile").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0]["profile"]
        return None
    except Exception as e:
        logger.warning("behavior_profile_load_failed", error=str(e))
        return None
