-- ============================================
-- ResuMax — Initial Database Schema
-- Run this in Supabase Dashboard > SQL Editor
-- ============================================

-- ── Table: profiles ─────────────────────────────────────────────
-- Extends Supabase Auth users with additional profile data
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT,
    email TEXT UNIQUE NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger: Auto-create profile on auth signup
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

-- ── Table: analyses ─────────────────────────────────────────────
-- Core entity — stores analysis inputs, pipeline state, and results
CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    
    -- Input
    resume_file_path TEXT NOT NULL,
    resume_text TEXT NOT NULL,
    job_description TEXT NOT NULL,
    job_title TEXT,
    
    -- Pipeline Status
    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending',
        'parsing',
        'scoring',
        'analyzing',
        'interviewing',
        'rewriting',
        'completed',
        'failed'
    )),
    current_step INTEGER DEFAULT 0,
    
    -- Results (all JSONB for schema flexibility)
    parsed_resume JSONB,
    ats_score INTEGER,
    ats_breakdown JSONB,
    keyword_analysis JSONB,
    skill_analysis JSONB,
    deep_analysis JSONB,
    star_rewrites JSONB,
    density_analysis JSONB,
    optimized_resume JSONB,
    
    -- SHRUTI
    shruti_conversation JSONB DEFAULT '[]'::jsonb,
    shruti_suggestions JSONB DEFAULT '[]'::jsonb,
    
    -- Metadata
    processing_time_ms INTEGER,
    model_used TEXT DEFAULT 'llama-3.3-70b-versatile',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Table: shruti_sessions ──────────────────────────────────────
-- Tracks interactive SHRUTI advisor conversations
CREATE TABLE IF NOT EXISTS shruti_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    
    messages JSONB DEFAULT '[]'::jsonb,
    pending_changes JSONB DEFAULT '[]'::jsonb,
    accepted_changes JSONB DEFAULT '[]'::jsonb,
    rejected_changes JSONB DEFAULT '[]'::jsonb,
    
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'expired')),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Row Level Security ──────────────────────────────────────────
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE shruti_sessions ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can only access their own profile
CREATE POLICY "profiles_own_data" ON profiles
    FOR ALL USING (auth.uid() = id);

-- Analyses: Users can only access their own analyses
CREATE POLICY "analyses_own_data" ON analyses
    FOR ALL USING (auth.uid() = user_id);

-- SHRUTI: Users can only access their own sessions
CREATE POLICY "shruti_own_data" ON shruti_sessions
    FOR ALL USING (auth.uid() = user_id);

-- ── Storage Bucket ──────────────────────────────────────────────
INSERT INTO storage.buckets (id, name, public) 
VALUES ('resumax-resumes', 'resumax-resumes', false)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: Users can only upload to their own folder
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
