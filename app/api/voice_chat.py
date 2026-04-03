"""
ResuMax Backend — Voice Chat API
AI-powered conversational resume advisor with neural TTS.
"""

import io
import base64
import structlog
import edge_tts
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.services.groq_client import (
    get_groq_balanced,
    get_groq_fast,
    call_llm_with_fallback,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/voice-chat", tags=["voice-chat"])

# Microsoft Edge Neural Voice — natural American female with emotions
TTS_VOICE = "en-US-JennyNeural"


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class VoiceChatRequest(BaseModel):
    question: str
    resume_context: str = ""
    conversation_history: list[ChatMessage] = []


SYSTEM_PROMPT = """You are Shruti, ResuMax's AI Resume Advisor. You're having a natural voice conversation with a user about their resume.

RULES:
- Keep responses concise and conversational (2-4 sentences max for voice)
- Be warm, encouraging, but honest about improvements
- Reference specific parts of their resume when answering
- If asked about improvements, give actionable, specific advice
- Use natural speaking patterns — no bullet points, no markdown
- If you don't have enough context, ask a follow-up question
- You're an expert in hiring, ATS systems, resume writing, and career strategy"""


async def generate_tts_audio(text: str) -> str:
    """Generate TTS audio using edge-tts and return base64-encoded mp3."""
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate="+5%", pitch="+0Hz")
    audio_buffer = io.BytesIO()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])

    audio_buffer.seek(0)
    return base64.b64encode(audio_buffer.read()).decode("utf-8")


@router.post("/ask")
async def voice_chat_ask(
    request: VoiceChatRequest,
    user: dict = Depends(get_current_user),
):
    """Process a voice chat question about the user's resume."""
    logger.info("voice_chat_ask", user_id=user["id"], question_len=len(request.question))

    # Build conversation context
    history_text = ""
    for msg in request.conversation_history[-10:]:  # Last 10 messages
        role_label = "User" if msg.role == "user" else "Shruti"
        history_text += f"{role_label}: {msg.content}\n"

    prompt = f"""RESUME CONTEXT:
{request.resume_context[:5000] if request.resume_context else "No resume uploaded yet."}

CONVERSATION HISTORY:
{history_text if history_text else "This is the start of the conversation."}

USER'S QUESTION: {request.question}

Respond naturally as Shruti, the AI resume advisor. Keep it short and conversational for voice output."""

    response = await call_llm_with_fallback(
        primary=get_groq_balanced(),
        fallback=get_groq_fast(),
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        parse_json=False,
    )

    # Clean up response
    answer = response.strip().strip('"').strip("'")

    # Generate TTS audio
    try:
        audio_base64 = await generate_tts_audio(answer)
    except Exception as e:
        logger.warning("tts_generation_failed", error=str(e))
        audio_base64 = None

    logger.info("voice_chat_response", user_id=user["id"], response_len=len(answer))
    return {"answer": answer, "audio": audio_base64}
