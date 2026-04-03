"""
ResuMax — Groq LLM Client Service
Configures LangChain ChatGroq models with rate limiting.
"""

import json
import asyncio
import structlog
from time import time
from collections import deque
from typing import Optional, Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger(__name__)

# ── Rate Limiter ─────────────────────────────────────────────────

class RateLimiter:
    """Sliding window rate limiter for Groq API (25 RPM with headroom)."""

    def __init__(self, rpm: int = 25):
        self.rpm = rpm
        self.timestamps: deque = deque()

    async def acquire(self):
        """Wait if rate limit would be exceeded."""
        now = time()
        # Remove timestamps older than 60 seconds
        while self.timestamps and self.timestamps[0] < now - 60:
            self.timestamps.popleft()

        if len(self.timestamps) >= self.rpm:
            sleep_time = 60 - (now - self.timestamps[0])
            if sleep_time > 0:
                logger.info("rate_limit_wait", sleep_seconds=round(sleep_time, 1))
                await asyncio.sleep(sleep_time)

        self.timestamps.append(time())


# ── Singleton instances ──────────────────────────────────────────

_groq_fast: Optional[ChatGroq] = None
_groq_balanced: Optional[ChatGroq] = None
_rate_limiter = RateLimiter(rpm=14)


def get_groq_fast() -> ChatGroq:
    """Get the fast Groq model (8B) for simple extraction tasks."""
    global _groq_fast
    if _groq_fast is None:
        settings = get_settings()
        _groq_fast = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0,
            max_tokens=2048,
            groq_api_key=settings.groq_api_key,
        )
        logger.info("groq_fast_initialized", model="llama-3.1-8b-instant")
    return _groq_fast


def get_groq_balanced() -> ChatGroq:
    """Get the balanced Groq model (70B) for reasoning tasks."""
    global _groq_balanced
    if _groq_balanced is None:
        settings = get_settings()
        _groq_balanced = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=4096,
            groq_api_key=settings.groq_api_key,
        )
        logger.info("groq_balanced_initialized", model="llama-3.3-70b-versatile")
    return _groq_balanced


# ── LLM Call Helpers ─────────────────────────────────────────────

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
async def call_llm(llm: ChatGroq, prompt: str, system_prompt: str = "") -> str:
    """
    Call an LLM with rate limiting and retry logic.
    Returns the raw text response.
    """
    await _rate_limiter.acquire()

    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    start = time()
    response = llm.invoke(messages)
    elapsed = int((time() - start) * 1000)

    logger.info(
        "llm_call_complete",
        model=llm.model_name,
        elapsed_ms=elapsed,
        response_chars=len(response.content),
    )
    return response.content


async def call_llm_json(llm: ChatGroq, prompt: str, system_prompt: str = "") -> dict:
    """
    Call an LLM and parse the response as JSON.
    Handles markdown code fences and partial JSON.
    """
    raw = await call_llm(llm, prompt, system_prompt)

    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("json_parse_failed", error=str(e), raw_preview=text[:200])
        # Try to find JSON object in the response
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1
        if start_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(text[start_idx:end_idx])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Failed to parse LLM response as JSON: {e}")


async def call_llm_with_fallback(
    primary: ChatGroq,
    fallback: ChatGroq,
    prompt: str,
    system_prompt: str = "",
    parse_json: bool = True,
) -> Any:
    """
    Call primary LLM, fall back to secondary on failure.
    Returns parsed JSON dict or raw string based on parse_json flag.
    """
    call_fn = call_llm_json if parse_json else call_llm

    try:
        return await call_fn(primary, prompt, system_prompt)
    except Exception as primary_err:
        logger.warning(
            "primary_llm_failed",
            model=primary.model_name,
            error=str(primary_err),
        )
        try:
            return await call_fn(fallback, prompt, system_prompt)
        except Exception as fallback_err:
            logger.error(
                "fallback_llm_failed",
                model=fallback.model_name,
                error=str(fallback_err),
            )
            raise fallback_err
