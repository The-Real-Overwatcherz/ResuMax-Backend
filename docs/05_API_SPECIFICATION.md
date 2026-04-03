# ResuMax — API Specification & Frontend Integration

## API Base URL
```
Development: http://localhost:8000
Production:  https://resumax-api.onrender.com  (or Railway equivalent)
```

## Authentication

All API calls (except health check) require a Supabase JWT token:
```
Authorization: Bearer <supabase_access_token>
```

The Python backend verifies tokens using `supabase.auth.get_user(token)`.

---

## REST Endpoints

### Health Check
```
GET /api/health
Response: { "status": "ok", "version": "1.0.0" }
```

### Auth Verification
```
POST /api/auth/verify
Headers: Authorization: Bearer <token>
Response: { "user_id": "uuid", "email": "john@example.com" }
```

---

### Analysis Endpoints

#### Start Analysis
```
POST /api/analysis/start
Content-Type: multipart/form-data

Body:
  resume: File (PDF, DOCX, or TXT, max 10MB)
  job_description: String (pasted JD text)

Response (201):
{
    "analysis_id": "uuid",
    "status": "pending",
    "message": "Analysis pipeline started. Subscribe to realtime channel for updates.",
    "realtime_channel": "analysis:{analysis_id}"
}

Errors:
  400 — Invalid file type or missing JD
  401 — Invalid/expired token
  413 — File too large (>10MB)
  429 — Rate limited (max 5 active analyses per user)
```

#### Get Analysis Results
```
GET /api/analysis/{analysis_id}

Response (200):
{
    "id": "uuid",
    "status": "completed",
    "created_at": "2026-04-02T17:00:00Z",
    
    "ats_score": 62,
    "ats_breakdown": {
        "keyword_score": 70,
        "section_completeness": 100,
        "format_compliance": 75,
        "action_verb_usage": 45,
        "quantification_rate": 30,
        "final_score": 62
    },
    
    "keyword_analysis": {
        "total_found": 12,
        "total_missing": 8,
        "matches": [
            { "keyword": "Python", "found": true, "location": "skills", "importance": "critical" },
            { "keyword": "Kubernetes", "found": false, "importance": "critical" }
        ]
    },
    
    "skill_analysis": {
        "exact_matches": ["Python", "React", "Docker"],
        "synonym_matches": [{ "resume": "PostgreSQL", "jd": "SQL databases" }],
        "implicit_skills": [{ "skill": "Leadership", "evidence": "Led team of 8..." }],
        "missing_critical": ["Kubernetes", "Terraform"],
        "missing_optional": ["GraphQL"],
        "recommendations": ["Add Kubernetes to your skills section"]
    },
    
    "deep_analysis": {
        "experience_level_match": "match",
        "industry_alignment": 75,
        "strengths": ["Strong quantified achievements", "Relevant tech stack"],
        "weaknesses": ["No cloud infrastructure experience mentioned"],
        "gap_analysis": [{ "area": "DevOps", "gap_description": "...", "suggestion": "..." }],
        "overall_assessment": "Solid mid-level candidate with..."
    },
    
    "bullet_rewrites": [
        {
            "original": "Responsible for managing the frontend team",
            "rewritten": "Directed a 6-person frontend engineering team...",
            "company": "Acme Corp",
            "improvement_type": "star-format",
            "keywords_added": ["cross-functional"],
            "confidence": 0.85,
            "reasoning": "Added team size and quantified outcome"
        }
    ],
    
    "density_analysis": {
        "overall_density_score": 72,
        "over_stuffed_keywords": [],
        "under_represented": ["Kubernetes", "agile"]
    },
    
    "optimized_resume": { /* Full optimized ParsedResume structure */ },
    "final_ats_score": 84,
    "score_improvement": 22,
    
    "jarvis_available": true,
    "total_suggestions": 14,
    
    "processing_time_ms": 45000,
    "model_used": "llama-3.3-70b-versatile"
}

Errors:
  404 — Analysis not found
  403 — Analysis belongs to another user
```

#### Get Analysis Status (lightweight poll)
```
GET /api/analysis/{analysis_id}/status

Response (200):
{
    "status": "scoring",
    "current_step": 2,
    "total_steps": 6,
    "step_label": "Calculating ATS Score",
    "estimated_remaining_seconds": 30
}
```

#### Get Analysis History
```
GET /api/history?page=1&limit=10

Response (200):
{
    "analyses": [
        {
            "id": "uuid",
            "job_title": "Senior Frontend Engineer",
            "ats_score": 62,
            "final_ats_score": 84,
            "status": "completed",
            "created_at": "2026-04-02T17:00:00Z"
        }
    ],
    "total": 15,
    "page": 1,
    "limit": 10
}
```

---

### JARVIS Endpoints

#### Start JARVIS Session
```
POST /api/jarvis/start/{analysis_id}

Response (201):
{
    "session_id": "uuid",
    "websocket_url": "ws://localhost:8000/ws/jarvis/{session_id}",
    "realtime_channel": "jarvis:{session_id}"
}

Errors:
  400 — Analysis not completed yet
  404 — Analysis not found
  409 — Active JARVIS session already exists for this analysis
```

#### Get Session Summary
```
GET /api/jarvis/{session_id}/summary

Response (200):
{
    "session_id": "uuid",
    "analysis_id": "uuid",
    "status": "completed",
    "original_score": 62,
    "final_score": 84,
    "improvement": 22,
    "total_suggestions": 14,
    "accepted": 9,
    "rejected": 5,
    "conversation_messages": 28,
    "duration_minutes": 12
}
```

---

### Export Endpoints

#### Download Optimized Resume (PDF)
```
GET /api/export/{analysis_id}/pdf

Response: application/pdf binary stream
Headers:
  Content-Disposition: attachment; filename="resume_optimized.pdf"
```

#### Download Optimized Resume (DOCX)
```
GET /api/export/{analysis_id}/docx

Response: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Headers:
  Content-Disposition: attachment; filename="resume_optimized.docx"
```

---

## WebSocket: JARVIS Real-time

### Connection
```
WS /ws/jarvis/{session_id}
Query: ?token={supabase_access_token}
```

### Client → Server
```json
// Accept suggestion
{"action": "accept", "suggestion_id": "bullet_a1b2c3d4"}

// Reject suggestion
{"action": "reject", "suggestion_id": "bullet_a1b2c3d4"}

// Send message
{"action": "message", "text": "Can you make it more technical?"}

// Voice input (base64 encoded audio)
{"action": "voice", "audio_base64": "UklGRi..."}

// Accept all remaining
{"action": "apply_all"}

// End session
{"action": "end_session"}
```

### Server → Client
```json
// JARVIS speaking
{
    "type": "jarvis_message",
    "text": "Good evening, sir. I've analyzed your resume...",
    "voice_url": null
}

// New suggestion card
{
    "type": "suggestion",
    "suggestion": {
        "id": "bullet_a1b2c3d4",
        "category": "bullet_rewrite",
        "title": "Rewrite bullet in Acme Corp",
        "description": "...",
        "before": "Managed the dev team",
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
{"type": "typing", "is_typing": true}

// Session complete
{
    "type": "session_summary",
    "stats": {
        "original_score": 62,
        "final_score": 84,
        "improvement": 22,
        "accepted": 9,
        "rejected": 5
    }
}
```

---

## Realtime: Pipeline Progress

### Channel: `analysis:{analysis_id}`

The frontend subscribes to this channel to show live pipeline progress.

```typescript
// Frontend subscription
import { supabase } from '@/lib/supabase'

const channel = supabase.channel(`analysis:${analysisId}`)

channel.on('broadcast', { event: 'progress' }, ({ payload }) => {
    // payload = { step, status, message, percentage }
    setPipelineStep(payload.step)
    setStatusMessage(payload.message)
})

channel.on('broadcast', { event: 'completed' }, ({ payload }) => {
    // payload = { analysis_id, ats_score, total_suggestions }
    router.push(`/dashboard?id=${payload.analysis_id}`)
})

channel.on('broadcast', { event: 'error' }, ({ payload }) => {
    // payload = { error_message, failed_at_step }
    showError(payload.error_message)
})

channel.subscribe()
```

### Progress Events (sent by backend)

| Step | Event Data |
|---|---|
| 1 | `{ step: 1, status: 'parsing', message: 'Extracting resume data...', percentage: 15 }` |
| 2 | `{ step: 2, status: 'scoring', message: 'Calculating ATS score...', percentage: 30 }` |
| 3 | `{ step: 3, status: 'analyzing', message: 'Running deep analysis...', percentage: 45 }` |
| 3b | `{ step: 3, status: 'analyzing', message: 'Matching skills semantically...', percentage: 55 }` |
| 4 | `{ step: 4, status: 'interviewing', message: 'Generating improvement questions...', percentage: 65 }` |
| 5 | `{ step: 5, status: 'rewriting', message: 'Rewriting bullet points...', percentage: 80 }` |
| 5b | `{ step: 5, status: 'rewriting', message: 'Checking keyword density...', percentage: 90 }` |
| 6 | `{ step: 6, status: 'completed', message: 'Optimization complete!', percentage: 100 }` |

---

## Frontend Integration: Supabase Client Setup

### Install
```bash
npm install @supabase/supabase-js
```

### Client (`lib/supabase.ts`)
```typescript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
```

### Auth Provider (`components/auth/AuthProvider.tsx`)
```typescript
'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { User, Session } from '@supabase/supabase-js'

interface AuthContextType {
    user: User | null
    session: Session | null
    loading: boolean
    signUp: (email: string, password: string, fullName: string) => Promise<void>
    signIn: (email: string, password: string) => Promise<void>
    signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType>(/* ... */)

export function AuthProvider({ children }) {
    const [user, setUser] = useState<User | null>(null)
    const [session, setSession] = useState<Session | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        // Get initial session
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSession(session)
            setUser(session?.user ?? null)
            setLoading(false)
        })

        // Listen for auth changes
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            (_event, session) => {
                setSession(session)
                setUser(session?.user ?? null)
            }
        )

        return () => subscription.unsubscribe()
    }, [])

    const signUp = async (email: string, password: string, fullName: string) => {
        const { error } = await supabase.auth.signUp({
            email,
            password,
            options: { data: { full_name: fullName } }
        })
        if (error) throw error
    }

    const signIn = async (email: string, password: string) => {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
    }

    const signOut = async () => {
        await supabase.auth.signOut()
    }

    return (
        <AuthContext.Provider value={{ user, session, loading, signUp, signIn, signOut }}>
            {children}
        </AuthContext.Provider>
    )
}

export const useAuth = () => useContext(AuthContext)
```

### Protected Route (`components/auth/ProtectedRoute.tsx`)
```typescript
'use client'

import { useAuth } from './AuthProvider'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { user, loading } = useAuth()
    const router = useRouter()

    useEffect(() => {
        if (!loading && !user) {
            router.push('/login')
        }
    }, [user, loading, router])

    if (loading) return <div className="min-h-screen bg-[#080808]" /> // Loading state
    if (!user) return null

    return <>{children}</>
}
```

---

## Environment Variables

### Frontend (`.env.local`)
```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGci...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (`.env`)
```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
GROQ_API_KEY=gsk_xxxxx

# Optional (for voice features)
# No additional keys needed — Edge TTS is keyless, Groq Whisper uses same API key
```
