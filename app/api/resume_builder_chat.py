import json
import structlog
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.groq_client import get_groq_balanced, call_llm_json
from app.api.deps import get_current_user
from app.services.behavior_profiler import (
    get_or_analyze_profile,
    build_adaptive_prompt,
    save_profile_to_db,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/resume-builder", tags=["Resume Builder"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    current_resume_data: Dict[str, Any]

class ChatResponse(BaseModel):
    ai_reply: str
    updated_resume_data: Dict[str, Any]

SYSTEM_PROMPT = """
You are Shruti, an expert ATS (Applicant Tracking System) AI resume consultant inside the ResuMax platform.
Your goal is to guide the user in building a high-scoring resume by asking simple, targeted questions one at a time.
Do not ask them to fill out forms; ask conversational questions.
Focus on extracting: Contact Info, Summary, Experience (Company, Title, Dates, Bullets), Education, Skills, and Projects.
When the user provides information, update the `current_resume_data` accordingly. Make sure to format their experience bullet points powerfully using action verbs and metrics.

You MUST always return a valid JSON object matching this schema exactly:
{
  "ai_reply": "Your conversational response and the next question.",
  "updated_resume_data": {
    "contact": {"full_name": "", "email": "", "phone": "", "linkedin": "", "location": ""},
    "summary": "",
    "experience": [{"id": "...", "company": "", "title": "", "dates": "", "bullets": [], "is_current": false}],
    "education": [{"id": "...", "institution": "", "degree": "", "field": "", "dates": "", "gpa": ""}],
    "skills": [],
    "certifications": [],
    "projects": [{"id": "...", "name": "", "description": "", "link": ""}],
    "languages": []
  }
}

Keep your `ai_reply` concise, friendly, and focused. Only ask one question at a time.
"""

@router.post("/chat", response_model=ChatResponse)
async def resume_chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    try:
        llm = get_groq_balanced()

        # ── Behavioral AI: analyze user's communication style ──
        history_dicts = [{"role": m.role, "content": m.content} for m in request.messages]
        behavior_profile = await get_or_analyze_profile(user["id"], history_dicts)
        adaptive_system_prompt = build_adaptive_prompt(SYSTEM_PROMPT, behavior_profile)
        logger.info("builder_behavior_adapted", user_id=user["id"], profile=behavior_profile)

        if len(request.messages) % 5 == 0 and request.messages:
            await save_profile_to_db(user["id"], behavior_profile)

        # Format conversation history
        chat_history_str = ""
        for msg in request.messages[-5:]:  # Last 5 messages for context
            chat_history_str += f"{msg.role.capitalize()}: {msg.content}\n"

        user_prompt = f"""
Current Resume Data:
{json.dumps(request.current_resume_data, indent=2)}

Conversation History:
{chat_history_str}

Please respond with the JSON containing your next 'ai_reply' and the fully 'updated_resume_data'.
"""

        response_data = await call_llm_json(
            llm=llm,
            prompt=user_prompt,
            system_prompt=adaptive_system_prompt
        )
        
        if "ai_reply" not in response_data or "updated_resume_data" not in response_data:
            raise ValueError("LLM returned incomplete JSON.")
            
        return ChatResponse(
            ai_reply=response_data["ai_reply"],
            updated_resume_data=response_data["updated_resume_data"]
        )
        
    except Exception as e:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.error("resume_chat_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to process chat")
