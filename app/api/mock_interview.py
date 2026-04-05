"""
ResuMax Backend — Mock Interview API
Shruti conducts a live mock interview based on the user's resume using Groq.
"""

import structlog
import io
import base64
import edge_tts
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
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
router = APIRouter(prefix="/api/mock-interview", tags=["mock-interview"])

TTS_VOICE = "en-US-JennyNeural"


class InterviewMessage(BaseModel):
    role: str  # "interviewer" or "candidate"
    content: str


class StartInterviewRequest(BaseModel):
    resume_context: str = ""
    job_role: str = ""


class RespondRequest(BaseModel):
    resume_context: str = ""
    job_role: str = ""
    answer: str
    conversation_history: list[InterviewMessage] = []


INTERVIEW_SYSTEM_PROMPT = """You are Shruti, a senior technical interviewer at a top-tier company.
You are conducting a LIVE MOCK INTERVIEW with a candidate. You have their resume in front of you.

INTERVIEW STYLE:
- Be professional, warm, but thorough — like a real interviewer
- Ask ONE question at a time — never multiple questions in one response
- Start with a brief introduction and an icebreaker question about themselves
- Then move through: background questions → technical/skill questions → behavioral (STAR method) → situational → closing
- Base ALL questions on the candidate's actual resume — their projects, skills, experience, education
- After the candidate answers, give brief feedback (1-2 sentences) then ask the next question
- If the answer is weak, gently probe deeper or offer constructive tips
- After 8-10 questions, wrap up the interview with a summary and rating

FEEDBACK FORMAT (after each answer):
- Give a brief assessment: ✅ Strong, ⚠️ Needs improvement, or 💡 Tip
- Then immediately follow with the next question

IMPORTANT:
- Never break character — you ARE the interviewer
- Reference specific items from their resume (projects, companies, skills)
- Keep responses concise — this is a conversation, not an essay
- If a job role is specified, tailor questions to that role
- Do NOT use markdown headers or heavy formatting — keep it conversational
"""


async def generate_tts_audio(text: str) -> str:
    """Generate TTS audio using edge-tts and return base64-encoded mp3."""
    # Strip emojis and special chars for cleaner TTS
    clean_text = text.replace("✅", "").replace("⚠️", "").replace("💡", "").replace("🎯", "").strip()
    communicate = edge_tts.Communicate(clean_text, TTS_VOICE, rate="+5%", pitch="+0Hz")
    audio_buffer = io.BytesIO()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])

    audio_buffer.seek(0)
    return base64.b64encode(audio_buffer.read()).decode("utf-8")


@router.post("/start")
async def start_interview(
    request: StartInterviewRequest,
    user: dict = Depends(get_current_user),
):
    """Start a mock interview session — Shruti introduces herself and asks the first question."""
    logger.info(
        "mock_interview_start",
        user_id=user["id"],
        resume_len=len(request.resume_context),
        job_role=request.job_role,
    )

    # ── Behavioral AI: load any existing profile for this user ──
    from app.services.behavior_profiler import load_profile_from_db, _default_profile
    saved_profile = await load_profile_from_db(user["id"])
    adaptive_system_prompt = build_adaptive_prompt(
        INTERVIEW_SYSTEM_PROMPT,
        saved_profile or _default_profile()
    )

    role_context = f"\nThe candidate is interviewing for the role of: {request.job_role}" if request.job_role else ""

    prompt = f"""CANDIDATE'S RESUME:
{request.resume_context[:5000] if request.resume_context else "No resume provided."}
{role_context}

Begin the mock interview. Introduce yourself briefly as the interviewer, make the candidate comfortable with a warm opener, and then ask your FIRST interview question based on their resume.
Keep it to 3-4 sentences max."""

    response = await call_llm_with_fallback(
        primary=get_groq_balanced(),
        fallback=get_groq_fast(),
        prompt=prompt,
        system_prompt=adaptive_system_prompt,
        parse_json=False,
    )

    answer = response.strip().strip('"').strip("'")

    # Generate TTS
    audio_base64 = None
    try:
        audio_base64 = await generate_tts_audio(answer)
    except Exception as e:
        logger.warning("tts_generation_failed", error=str(e))

    return {"message": answer, "audio": audio_base64}


@router.post("/respond")
async def respond_to_answer(
    request: RespondRequest,
    user: dict = Depends(get_current_user),
):
    """Process the candidate's answer and provide feedback + next question."""
    logger.info(
        "mock_interview_respond",
        user_id=user["id"],
        answer_len=len(request.answer),
        history_len=len(request.conversation_history),
    )

    # ── Behavioral AI: analyze candidate's communication style ──
    history_dicts = [{"role": "user" if m.role == "candidate" else "assistant", "content": m.content} for m in request.conversation_history]
    behavior_profile = await get_or_analyze_profile(user["id"], history_dicts)
    adaptive_system_prompt = build_adaptive_prompt(INTERVIEW_SYSTEM_PROMPT, behavior_profile)
    logger.info("interview_behavior_adapted", user_id=user["id"], profile=behavior_profile)

    if len(request.conversation_history) % 5 == 0 and request.conversation_history:
        await save_profile_to_db(user["id"], behavior_profile)

    role_context = f"\nThe candidate is interviewing for the role of: {request.job_role}" if request.job_role else ""

    # Build conversation history
    history_text = ""
    for msg in request.conversation_history[-20:]:
        role_label = "Interviewer (Shruti)" if msg.role == "interviewer" else "Candidate"
        history_text += f"{role_label}: {msg.content}\n"

    question_count = sum(1 for m in request.conversation_history if m.role == "interviewer")

    if question_count >= 9:
        prompt = f"""CANDIDATE'S RESUME:
{request.resume_context[:5000] if request.resume_context else "No resume provided."}
{role_context}

INTERVIEW SO FAR:
{history_text}

Candidate's latest answer: {request.answer}

This is the FINAL question. Give brief feedback on their last answer, then WRAP UP the interview:
- Thank the candidate
- Give an overall performance summary (strengths and areas to improve)
- Rate their interview performance out of 10
- Give 2-3 specific tips for improvement
Keep it concise but helpful."""
    else:
        prompt = f"""CANDIDATE'S RESUME:
{request.resume_context[:5000] if request.resume_context else "No resume provided."}
{role_context}

INTERVIEW SO FAR:
{history_text}

Candidate's latest answer: {request.answer}

Give brief feedback on their answer (1-2 sentences with ✅/⚠️/💡), then ask the NEXT interview question.
This is question {question_count + 1} of approximately 10.
Remember to base your questions on their actual resume content.
Keep your total response to 3-5 sentences."""

    response = await call_llm_with_fallback(
        primary=get_groq_balanced(),
        fallback=get_groq_fast(),
        prompt=prompt,
        system_prompt=adaptive_system_prompt,
        parse_json=False,
    )

    answer = response.strip().strip('"').strip("'")
    is_complete = question_count >= 9

    # Generate TTS (skip for very long wrap-up)
    audio_base64 = None
    if len(answer) < 800:
        try:
            audio_base64 = await generate_tts_audio(answer)
        except Exception as e:
            logger.warning("tts_generation_failed", error=str(e))

    return {
        "message": answer,
        "audio": audio_base64,
        "is_complete": is_complete,
        "question_number": question_count + 1,
    }
