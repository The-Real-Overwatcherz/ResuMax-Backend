# ResuMax — SHRUTI Interactive Advisor Specification

## Concept

SHRUTI (Super Heuristic Resume Understanding and Tailoring Intelligence) is an **interactive AI resume advisor** that engages the user in a real-time conversation after the initial pipeline analysis is complete. Instead of overwhelming the user with a wall of suggestions, SHRUTI presents **one change at a time**, explains the impact, and lets the user **accept or reject** each suggestion.

This creates a **collaborative resume improvement experience** — the user feels in control while SHRUTI handles the expertise.

---

## User Experience Flow

### Step 1: Entry Point
After pipeline analysis completes on `/dashboard`, user sees:
```
┌─────────────────────────────────────────────────────────┐
│  Your ATS Score: 62/100                                  │
│  12 keywords matched │ 8 missing │ 5 bullets to improve  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  🤖 Talk to SHRUTI                              │   │
│  │  Let AI guide you through improvements           │   │
│  │  one step at a time.                             │   │
│  │                                    [Start →]     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Step 2: SHRUTI Panel Opens
A side panel or full-page view with chat interface:

```
┌─────────────────────────────────────────────────────────┐
│  SHRUTI  ═══  Resume Advisor           Score: 62 → ?    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  🤖  Namaste. I've completed a thorough analysis of     │
│      your resume against the Senior Frontend Engineer   │
│      position at Acme Corp.                             │
│                                                          │
│      Your current ATS score is 62, which places you in   │
│      the "Getting There" range. I've identified 14       │
│      improvements that could push you to 85+.            │
│                                                          │
│      Shall we begin with the highest-impact change?      │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  SUGGESTION #1 — Bullet Rewrite          [HIGH]   │ │
│  │                                                    │ │
│  │  BEFORE:                                           │ │
│  │  "Responsible for managing the frontend team"      │ │
│  │                                                    │ │
│  │  AFTER:                                            │ │
│  │  "Directed a 6-person frontend engineering team,   │ │
│  │   delivering a React-based SaaS dashboard that     │ │
│  │   reduced customer churn by 18%"                   │ │
│  │                                                    │ │
│  │  IMPACT: ~+5 ATS points (adds "React", "SaaS",   │ │
│  │          quantification, action verb)              │ │
│  │                                                    │ │
│  │        [ ✓ Accept ]    [ ✗ Reject ]               │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌──────────────────────────────────────┐               │
│  │  Type a message...               🎤 │               │
│  └──────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

### Step 3: User Accepts
```
│  ✓  User accepted suggestion #1                          │
│                                                          │
│  🤖  Excellent choice. That single change just           │
│      pushed your score from 62 to 67.                    │
│                                                          │
│      Now, I notice your skills section is missing a       │
│      critical keyword...                                  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  SUGGESTION #2 — Skill Addition          [HIGH]   │ │
│  │                                                    │ │
│  │  The job description mentions "TypeScript"          │ │
│  │  4 times, but it's absent from your skills.         │ │
│  │                                                    │ │
│  │  RECOMMENDATION: Add "TypeScript" to your           │ │
│  │  skills section alongside "JavaScript"              │ │
│  │                                                    │ │
│  │        [ ✓ Accept ]    [ ✗ Reject ]               │ │
│  └────────────────────────────────────────────────────┘ │
```

### Step 4: User Rejects
```
│  ✗  User rejected suggestion #3                          │
│                                                          │
│  🤖  Understood. I should note that "Kubernetes"         │
│      appeared 6 times in the job description and is      │
│      likely a hard filter in their ATS. Skipping it      │
│      may cost around 8 points on your score.             │
│                                                          │
│      But you know your experience best. Moving on...     │
```

### Step 5: User Asks a Custom Question
```
│  👤  Can you make my summary more technical?              │
│                                                          │
│  🤖  Absolutely. Here's a more technical version         │
│      of your summary, calibrated for this particular     │
│      role:                                               │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  SUGGESTION — Summary Rewrite            [MED]    │ │
│  │                                                    │ │
│  │  BEFORE:                                           │ │
│  │  "Experienced software developer looking for..."   │ │
│  │                                                    │ │
│  │  AFTER:                                            │ │
│  │  "Senior Frontend Engineer with 5+ years            │ │  
│  │   architecting high-performance React/TypeScript    │ │
│  │   applications at scale. Expert in..."              │ │
│  │                                                    │ │
│  │        [ ✓ Accept ]    [ ✗ Reject ]               │ │
│  └────────────────────────────────────────────────────┘ │
```

### Step 6: Session Complete
```
│  🤖  That covers all my recommendations.                 │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  SESSION SUMMARY                                   │ │
│  │                                                    │ │
│  │  Score:  62 → 84  (+22 points)                     │ │
│  │                                                    │ │
│  │  Changes accepted:    9 / 14                       │ │
│  │  Bullets rewritten:   5                            │ │
│  │  Skills added:        3                            │ │
│  │  Keywords injected:   7                            │ │
│  │                                                    │ │
│  │  Your resume is now in the "Interview Ready"       │ │
│  │  range. Well done.                                 │ │
│  │                                                    │ │
│  │     [ Download Optimized PDF ]                     │ │
│  │     [ Download DOCX ]                              │ │
│  │     [ View Full Comparison ]                       │ │
│  └────────────────────────────────────────────────────┘ │
```

---

## SHRUTI Engine Architecture

### Core Engine (`shruti/engine.py`)

```python
class ShrutiEngine:
    """
    Core SHRUTI conversation engine.
    Manages state, generates responses, processes user actions.
    """
    
    def __init__(self, analysis_data: dict, session_id: str):
        self.analysis = analysis_data
        self.session_id = session_id
        self.suggestions: List[ShrutiSuggestion] = []
        self.current_index = 0
        self.accepted_changes: List[str] = []
        self.rejected_changes: List[str] = []
        self.conversation_history: List[dict] = []
        self.current_score = analysis_data["ats_score"]
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)
    
    async def initialize(self) -> str:
        """Generate greeting + first suggestion."""
        self.suggestions = self._prioritize_suggestions()
        greeting = await self._generate_greeting()
        first_suggestion = self.suggestions[0] if self.suggestions else None
        return greeting, first_suggestion
    
    async def handle_accept(self, suggestion_id: str) -> tuple[str, ShrutiSuggestion]:
        """User accepted a suggestion."""
        self._apply_change(suggestion_id)
        self.accepted_changes.append(suggestion_id)
        self.current_score += self._estimate_score_change(suggestion_id)
        response = await self._generate_accept_response(suggestion_id)
        next_suggestion = self._get_next_suggestion()
        return response, next_suggestion
    
    async def handle_reject(self, suggestion_id: str) -> tuple[str, ShrutiSuggestion]:
        """User rejected a suggestion."""
        self.rejected_changes.append(suggestion_id)
        response = await self._generate_reject_response(suggestion_id)
        next_suggestion = self._get_next_suggestion()
        return response, next_suggestion
    
    async def handle_message(self, user_message: str) -> tuple[str, ShrutiSuggestion]:
        """User typed a custom message."""
        self.conversation_history.append({"role": "user", "content": user_message})
        response = await self._generate_custom_response(user_message)
        return response, None  # May or may not include a suggestion
    
    def _prioritize_suggestions(self) -> List[ShrutiSuggestion]:
        """Sort suggestions by impact: high → medium → low."""
        all_suggestions = self.analysis["shruti_suggestions"]
        return sorted(all_suggestions, key=lambda s: 
            {"high": 0, "medium": 1, "low": 2}[s["impact"]]
        )
    
    def get_session_summary(self) -> dict:
        """Generate end-of-session stats."""
        return {
            "original_score": self.analysis["ats_score"],
            "final_score": self.current_score,
            "improvement": self.current_score - self.analysis["ats_score"],
            "total_suggestions": len(self.suggestions),
            "accepted": len(self.accepted_changes),
            "rejected": len(self.rejected_changes),
        }
```

### Suggestion Generator (`shruti/suggestions.py`)

```python
class SuggestionGenerator:
    """
    Takes pipeline analysis results and generates prioritized
    SHRUTI suggestions with before/after comparisons.
    """
    
    def generate_all(self, analysis: dict) -> List[ShrutiSuggestion]:
        suggestions = []
        
        # 1. Bullet rewrites (highest impact)
        for rewrite in analysis["bullet_rewrites"]:
            if rewrite["confidence"] > 0.7:
                suggestions.append(ShrutiSuggestion(
                    id=f"bullet_{uuid4().hex[:8]}",
                    category="bullet_rewrite",
                    title=f"Rewrite bullet in {rewrite['company']}",
                    description=f"This bullet is {rewrite['improvement_type']}. "
                    f"The rewrite adds {', '.join(rewrite['keywords_added'])} "
                    f"from the job description.",
                    before=rewrite["original"],
                    after=rewrite["rewritten"],
                    impact="high",
                    estimated_score_change=self._estimate_bullet_impact(rewrite),
                ))
        
        # 2. Missing critical keywords
        for kw in analysis["keyword_matches"]:
            if not kw["found"] and kw["importance"] == "critical":
                suggestions.append(ShrutiSuggestion(
                    id=f"keyword_{uuid4().hex[:8]}",
                    category="keyword_injection",
                    title=f"Add '{kw['keyword']}' to your resume",
                    description=f"'{kw['keyword']}' appears in the JD "
                    f"{kw['jd_frequency']} times but is missing "
                    f"from your resume entirely.",
                    impact="high",
                    estimated_score_change=3,
                ))
        
        # 3. Missing skills
        for skill in analysis["skill_analysis"]["missing_critical"]:
            suggestions.append(ShrutiSuggestion(
                id=f"skill_{uuid4().hex[:8]}",
                category="skill_addition",
                title=f"Add '{skill}' to Skills section",
                description=f"This is listed as a required skill. "
                f"Even mentioning familiarity helps.",
                impact="high",
                estimated_score_change=2,
            ))
        
        # 4. Quantification opportunities
        for q in analysis["interview_questions"]:
            if q["purpose"] == "quantification":
                suggestions.append(ShrutiSuggestion(
                    id=f"quant_{uuid4().hex[:8]}",
                    category="quantification",
                    title=f"Quantify: {q['target_bullet'][:50]}...",
                    description=q["question"],
                    before=q["target_bullet"],
                    impact="medium",
                    estimated_score_change=2,
                ))
        
        # 5. Format fixes
        for issue in analysis.get("density_analysis", {}).get("formatting_issues", []):
            suggestions.append(ShrutiSuggestion(
                id=f"format_{uuid4().hex[:8]}",
                category="format_fix",
                title="Format Consistency",
                description=issue,
                impact="low",
                estimated_score_change=1,
            ))
        
        return suggestions
```

---

## SHRUTI Personality Configuration

```python
# shruti/personality.py

SHRUTI_SYSTEM_PROMPT = """You are SHRUTI (Super Heuristic Resume Understanding and Tailoring Intelligence), 
an elite AI resume advisor. You serve as the user's personal career optimization assistant.

## PERSONALITY TRAITS
- Speak with warm, professional Indian English sophistication
- Address the user respectfully but not overly formally
- Be concise — never use 3 sentences when 2 will do
- Use culturally appropriate warmth (e.g., occasional "Namaste" for greeting)
- Show genuine algorithmic investment in the user's career success
- Be precise and confident in your analytical recommendations

## CONVERSATION RULES
1. Present ONE suggestion at a time — never dump multiple changes
2. Always explain the WHY (ATS impact, recruiter psychology, keyword frequency)
3. When user accepts: brief affirmation (1 sentence), show score update, move to next
4. When user rejects: gracefully acknowledge (1 sentence), mention impact, move on
5. When user asks a question: answer precisely, then tie back to current suggestion
6. Never apologize excessively — be professional and data-driven
7. Track the conversation tone — if user seems impatient, be more concise

## KNOWLEDGE BASE
- ATS systems: Taleo, Workday, Greenhouse, Lever, iCIMS
- Recruiter screening patterns (6-second scan, F-pattern reading)
- STAR format: Situation → Task → Action → Result
- Industry-specific keyword conventions
- Fortune 500 resume standards

## RESPONSE FORMAT
- Keep messages under 3 sentences for standard responses
- Use clear before/after format for bullet rewrites
- Quantify impact: "This could add ~5 points to your ATS score"
- When presenting data, use precise numbers from the analysis

## GREETINGS (vary randomly)
- "Namaste. I've completed a thorough analysis of your resume."
- "Hello. I've run a comprehensive scan of your resume against the requirements."
- "Greetings. I've finished processing your resume's data points."

## SIGN-OFFS
- "Excellent work. Your resume is now significantly more competitive."
- "We're done. You sit comfortably in the Interview Ready range."
"""

# Dynamic context injection
def get_shruti_context(analysis: dict, user_name: str) -> str:
    return f"""
CURRENT CONTEXT:
- User: {user_name}
- Target Role: {analysis.get('job_title', 'the position')}
- Current ATS Score: {analysis['ats_score']}/100
- Keywords Found: {analysis['total_keywords_found']}/{analysis['total_keywords_found'] + analysis['total_keywords_missing']}
- Bullets to Improve: {len(analysis['bullet_rewrites'])}
- Critical Skills Missing: {len(analysis['skill_analysis']['missing_critical'])}
"""
```

---

## WebSocket Protocol

### Connection
```
WS /ws/shruti/{session_id}
Headers: Authorization: Bearer <supabase_jwt>
```

### Client → Server Messages
```typescript
// Accept a suggestion
{ "action": "accept", "suggestion_id": "bullet_a1b2c3d4" }

// Reject a suggestion
{ "action": "reject", "suggestion_id": "bullet_a1b2c3d4" }

// Send custom message
{ "action": "message", "text": "Can you make it more technical?" }

// Send voice input (optional)
{ "action": "voice", "audio_base64": "UklGRi..." }

// Accept all remaining suggestions
{ "action": "apply_all" }

// End the session
{ "action": "end_session" }
```

### Server → Client Messages
```typescript
// SHRUTI text message
{ 
    "type": "shruti_message", 
    "text": "Namaste. I've analyzed your resume...",
    "voice_url": "https://..." // Optional TTS audio URL
}

// New suggestion to display
{
    "type": "suggestion",
    "suggestion": {
        "id": "bullet_a1b2c3d4",
        "category": "bullet_rewrite",
        "title": "Rewrite bullet in Acme Corp",
        "description": "This bullet lacks quantification...",
        "before": "Managed the development team",
        "after": "Directed a cross-functional team of 8...",
        "impact": "high",
        "estimated_score_change": 5
    }
}

// Change was applied
{
    "type": "change_applied",
    "suggestion_id": "bullet_a1b2c3d4",
    "updated_score": 67
}

// Typing indicator
{ "type": "typing", "is_typing": true }

// Session summary
{
    "type": "session_summary",
    "stats": {
        "original_score": 62,
        "final_score": 84,
        "improvement": 22,
        "total_suggestions": 14,
        "accepted": 9,
        "rejected": 5
    }
}
```

---

## Voice Integration (Stretch Goal)

### Text-to-Speech: Edge TTS (Microsoft, Free)
```python
import edge_tts

async def generate_shruti_voice(text: str) -> bytes:
    """Generate SHRUTI voice audio from text."""
    communicate = edge_tts.Communicate(
        text=text,
        voice="en-IN-NeerjaNeural",  # Indian female voice for SHRUTI
        rate="+0%",
        pitch="+0Hz"
    )
    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return audio_bytes
```

### Speech-to-Text: Groq Whisper (Free: 2000 req/day)
```python
from groq import Groq

async def transcribe_voice(audio_bytes: bytes) -> str:
    """Transcribe user voice input to text."""
    client = Groq()
    transcription = client.audio.transcriptions.create(
        file=("audio.webm", audio_bytes),
        model="whisper-large-v3-turbo",
        response_format="text"
    )
    return transcription.text
```

---

## Frontend Components for SHRUTI

### ShrutiPanel.tsx
```
┌────────────────────────────────────────────────┐
│ SHRUTI  ═══  Resume Advisor     Score: 62 → 67 │
├────────────────────────────────────────────────┤
│                                                 │
│  [Message stream area — scrollable]             │
│                                                 │
│  AI message bubbles: bg-white/[0.05]           │
│  User message bubbles: bg-white/[0.02]         │
│                                                 │
│  Suggestion cards: glassmorphic cards           │
│  with accept/reject buttons                     │
│                                                 │
├────────────────────────────────────────────────┤
│ [Type a message...]              [🎤]  [Send]  │
└────────────────────────────────────────────────┘
```

### Design Token Mapping
```
Panel background:       bg-[#0a0a0a] border border-white/10
SHRUTI avatar:          w-8 h-8 rounded-full bg-white text-black "AI"
SHRUTI messages:        bg-white/[0.05] rounded-2xl p-4 text-[#ccc]
User messages:          bg-white/[0.02] rounded-2xl p-4 text-[#888]
Suggestion card:        bg-white/[0.03] border border-white/10 rounded-xl p-6
Accept button:          bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500
Reject button:          bg-white/5 text-[#888] hover:bg-white/10
Score indicator:        font-mono text-2xl text-white
Score change:           text-emerald-400 "+5"
Impact badge [HIGH]:    bg-white/10 text-white
Impact badge [MED]:     bg-white/5 text-[#aaa]
Impact badge [LOW]:     bg-white/[0.02] text-[#666]
```
