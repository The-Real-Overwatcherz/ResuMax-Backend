"""
ResuMax Backend — Voice Chat API
AI-powered conversational resume advisor with neural TTS.
"""

import io
import base64
import structlog
import edge_tts
from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.services.file_parser import parse_resume_file
from app.services.groq_client import (
    get_groq_balanced,
    get_groq_fast,
    call_llm_with_fallback,
)
from app.services.behavior_profiler import (
    get_or_analyze_profile,
    build_adaptive_prompt,
    save_profile_to_db,
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
- Be warm, encouraging, but honest about improvements
- Reference specific parts of their resume when answering
- If asked about improvements, give actionable, specific advice
- If you don't have enough context, ask a follow-up question
- You're an expert in hiring, ATS systems, resume writing, career strategy, and skill development

SKILL ROADMAP GENERATION:
When users ask you to generate a learning roadmap, skill path, or how to learn specific skills, respond with a detailed, structured roadmap using MARKDOWN formatting:

Use this structure:
# 🗺️ Learning Roadmap: [Skill/Role]
**Estimated Timeline:** X months | **Difficulty:** Beginner → Advanced

## 📌 Phase 1: Foundation (Week 1-X)
**Goal:** [what they'll achieve]
- **Learn:** [topic 1], [topic 2]
- **Resources:**
  - 🎓 [Course name] — [platform] (free/paid)
  - 📖 [Documentation/book]
  - 🎥 [YouTube channel/video]
- **🛠️ Mini Project:** [hands-on project idea]
- **✅ Milestone:** [how to know they completed this phase]

(Repeat for Phase 2, 3, 4 etc.)

## 🎯 Final Goal
[summary of what they'll be able to do]

## 💡 Pro Tips
- [tip 1]
- [tip 2]

IMPORTANT: For roadmap requests, use rich markdown with emojis, headers, bold, lists, and clear structure. Make it detailed with real resource names.
For regular conversational questions, keep responses concise (2-4 sentences), warm, and natural. Do NOT use markdown for simple conversational replies."""


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
    logger.info("voice_chat_ask", user_id=user["id"], question_len=len(request.question), resume_context_len=len(request.resume_context))

    # ── Behavioral AI: analyze user's communication style ──
    history_dicts = [{"role": m.role, "content": m.content} for m in request.conversation_history]
    behavior_profile = await get_or_analyze_profile(user["id"], history_dicts)
    adaptive_system_prompt = build_adaptive_prompt(SYSTEM_PROMPT, behavior_profile)
    logger.info("behavior_adapted", user_id=user["id"], profile=behavior_profile)

    # Save profile periodically for cross-session persistence
    if len(request.conversation_history) % 5 == 0 and request.conversation_history:
        await save_profile_to_db(user["id"], behavior_profile)

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

Respond naturally as Shruti, the AI resume advisor."""

    # Detect if this is a roadmap/learning request
    roadmap_keywords = ['roadmap', 'learn', 'how to learn', 'skill path', 'study plan', 'learning path', 'guide me', 'how do i become', 'how to become', 'career path', 'upskill']
    is_roadmap_request = any(kw in request.question.lower() for kw in roadmap_keywords)

    if is_roadmap_request:
        prompt += "\n\nThis is a SKILL ROADMAP request. Generate a detailed, structured roadmap using markdown formatting with phases, resources, timelines, and project ideas. Be thorough and specific."
    else:
        prompt += "\nKeep it short and conversational for voice output."

    response = await call_llm_with_fallback(
        primary=get_groq_balanced(),
        fallback=get_groq_fast(),
        prompt=prompt,
        system_prompt=adaptive_system_prompt,
        parse_json=False,
    )

    # Clean up response
    answer = response.strip().strip('"').strip("'")

    # Generate TTS audio (skip for long roadmap responses to avoid timeout)
    audio_base64 = None
    if not is_roadmap_request or len(answer) < 500:
        try:
            audio_base64 = await generate_tts_audio(answer)
        except Exception as e:
            logger.warning("tts_generation_failed", error=str(e))
            audio_base64 = None

    logger.info("voice_chat_response", user_id=user["id"], response_len=len(answer), is_roadmap=is_roadmap_request)
    return {"answer": answer, "audio": audio_base64}


@router.post("/parse-resume")
async def parse_resume_for_chat(
    resume: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Parse an uploaded resume file and return the extracted text."""
    file_bytes = await resume.read()
    filename = resume.filename or "upload.pdf"
    text = parse_resume_file(file_bytes, filename)
    return {"text": text}
