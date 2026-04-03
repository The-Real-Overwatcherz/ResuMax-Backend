# ResuMax Backend — Supabase Architecture

## Overview

Supabase provides the entire persistence layer for ResuMax on the **free tier**:
- **Auth**: Email/password authentication with JWT
- **Database**: PostgreSQL with RLS (Row Level Security)
- **Storage**: File uploads for resumes
- **Realtime**: WebSocket channels for live pipeline progress

---

## Free Tier Constraints

| Resource | Limit | Our Usage |
|---|---|---|
| Database Storage | 500 MB | ~50MB (text-heavy, JSONB results) |
| File Storage | 1 GB | ~200MB (PDF/DOCX uploads) |
| Bandwidth (egress) | 5 GB/month | ~1GB for hackathon |
| Monthly Active Users | 50,000 | <100 for hackathon |
| Realtime Connections | 200 concurrent | <20 for hackathon |
| Realtime Messages | 2M/month | <10K for hackathon |
| Edge Function Invocations | 500K/month | Not used (Python backend instead) |
| Active Projects | 2 per org | 1 project |
| **Inactivity Pause** | **7 days** | Keep active during hackathon |

---

## Database Schema

### Table: `profiles`
Extends Supabase Auth users with additional profile data.

```sql
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT,
    email TEXT UNIQUE NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Trigger**: Auto-create profile on auth signup:
```sql
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (NEW.id, NEW.email, NEW.raw_user_meta_data->>'full_name');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();
```

### Table: `analyses`
Core entity — stores all analysis inputs, pipeline state, and results.

```sql
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    
    -- Input
    resume_file_path TEXT NOT NULL,
    resume_text TEXT NOT NULL,
    job_description TEXT NOT NULL,
    job_title TEXT,
    
    -- Pipeline Status
    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending',       -- Queued
        'parsing',       -- Node 1: Extracting resume data
        'scoring',       -- Node 2: ATS scoring
        'analyzing',     -- Node 3: Deep analysis + skills
        'interviewing',  -- Node 4: Generating interview questions
        'rewriting',     -- Node 5: Bullet rewrites + density check
        'completed',     -- All done
        'failed'         -- Error occurred
    )),
    current_step INTEGER DEFAULT 0,
    
    -- Results (all JSONB for schema flexibility)
    parsed_resume JSONB,       -- ParsedResume model
    ats_score INTEGER,         -- 0-100
    ats_breakdown JSONB,       -- {keyword_score, section_score, format_score, ...}
    keyword_analysis JSONB,    -- [{keyword, found, context, importance}, ...]
    skill_analysis JSONB,      -- {matched_skills, missing_skills, implicit_skills, ...}
    deep_analysis JSONB,       -- {strengths, weaknesses, gap_analysis, ...}
    star_rewrites JSONB,       -- [{original, rewritten, section, improvement_type}, ...]
    density_analysis JSONB,    -- {keyword_density, whitespace_balance, ...}
    optimized_resume JSONB,    -- Final optimized resume structure
    
    -- JARVIS
    jarvis_conversation JSONB DEFAULT '[]'::jsonb,
    jarvis_suggestions JSONB DEFAULT '[]'::jsonb,
    
    -- Metadata
    processing_time_ms INTEGER,
    model_used TEXT DEFAULT 'llama-3.3-70b-versatile',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Table: `jarvis_sessions`
Tracks interactive JARVIS advisor conversations.

```sql
CREATE TABLE jarvis_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    
    messages JSONB DEFAULT '[]'::jsonb,        -- Full conversation log
    pending_changes JSONB DEFAULT '[]'::jsonb, -- Current suggestions
    accepted_changes JSONB DEFAULT '[]'::jsonb,
    rejected_changes JSONB DEFAULT '[]'::jsonb,
    
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'expired')),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### JSONB Structure Examples

#### `parsed_resume` JSONB
```json
{
    "full_name": "John Doe",
    "email": "john@example.com",
    "phone": "+1-555-0123",
    "linkedin": "linkedin.com/in/johndoe",
    "summary": "Senior software engineer with 5+ years...",
    "experience": [
        {
            "title": "Work Experience",
            "content": [
                "Led team of 8 engineers to deliver microservices platform",
                "Reduced API latency by 40% through caching optimization"
            ],
            "raw_text": "..."
        }
    ],
    "education": [...],
    "skills": ["Python", "React", "Docker", "AWS"],
    "certifications": ["AWS Solutions Architect"]
}
```

#### `keyword_analysis` JSONB
```json
[
    {"keyword": "Python", "found": true, "context": "Skills section", "importance": "critical"},
    {"keyword": "Machine Learning", "found": false, "context": null, "importance": "important"},
    {"keyword": "cross-functional", "found": true, "context": "Experience bullet 3", "importance": "nice-to-have"}
]
```

#### `jarvis_suggestions` JSONB
```json
[
    {
        "id": "sug_001",
        "category": "bullet_rewrite",
        "description": "Your bullet about 'managing the team' lacks quantification",
        "before": "Managed a team of developers",
        "after": "Directed a cross-functional team of 8 engineers, delivering 3 microservices 2 weeks ahead of schedule",
        "impact": "high",
        "accepted": null
    }
]
```

---

## Row Level Security (RLS) Policies

```sql
-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE jarvis_sessions ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can only access their own profile
CREATE POLICY "profiles_own_data" ON profiles
    FOR ALL USING (auth.uid() = id);

-- Analyses: Users can only access their own analyses
CREATE POLICY "analyses_own_data" ON analyses
    FOR ALL USING (auth.uid() = user_id);

-- JARVIS: Users can only access their own sessions
CREATE POLICY "jarvis_own_data" ON jarvis_sessions
    FOR ALL USING (auth.uid() = user_id);

-- Service role bypass: Python backend uses service_role key
-- which bypasses RLS for pipeline writes
```

---

## Storage Configuration

### Bucket: `resumax-resumes`

```sql
-- Create bucket (via Supabase dashboard or SQL)
INSERT INTO storage.buckets (id, name, public) 
VALUES ('resumax-resumes', 'resumax-resumes', false);

-- RLS: Users can only upload to their own folder
CREATE POLICY "users_upload_own" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'resumax-resumes' AND
        auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "users_read_own" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'resumax-resumes' AND
        auth.uid()::text = (storage.foldername(name))[1]
    );
```

### File Path Convention
```
resumax-resumes/
  └── {user_id}/
      └── {analysis_id}/
          ├── original.pdf       # User's uploaded resume
          └── optimized.pdf      # Generated optimized resume
```

### File Size Limits
- Max upload: 10MB per file
- Accepted types: `.pdf`, `.docx`, `.txt`

---

## Realtime Channels

### Channel: `analysis:{analysis_id}`
Used to stream pipeline progress to the frontend.

```typescript
// Frontend subscription
const channel = supabase.channel(`analysis:${analysisId}`)
channel.on('broadcast', { event: 'progress' }, (payload) => {
    // payload.data = { step: 2, status: 'scoring', message: 'Calculating ATS score...' }
    updateProgress(payload.data)
})
channel.subscribe()
```

```python
# Backend broadcast (Python)
supabase.realtime.channel(f"analysis:{analysis_id}").send_broadcast(
    event="progress",
    data={"step": 2, "status": "scoring", "message": "Calculating ATS score..."}
)
```

### Channel: `jarvis:{session_id}`
Used for bidirectional JARVIS conversation.

```typescript
// Frontend: Send message
channel.send({ type: 'broadcast', event: 'user_action', payload: {
    action: 'accept', suggestion_id: 'sug_001'
}})

// Frontend: Receive JARVIS response
channel.on('broadcast', { event: 'jarvis_response' }, (payload) => {
    // payload.data = { type: 'jarvis_message', text: '...', suggestion: {...} }
})
```

---

## Supabase Client Configuration

### Frontend (TypeScript)
```typescript
// lib/supabase.ts
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
```

### Backend (Python)
```python
# services/supabase.py
from supabase import create_client, Client

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Service role bypasses RLS
)
```

---

## Environment Variables

### Frontend (.env.local)
```
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGci...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (.env)
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
GROQ_API_KEY=gsk_xxxxx
```
