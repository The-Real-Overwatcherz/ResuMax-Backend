-- Profile Reports Table
-- Stores LinkedIn and GitHub profile analysis reports

CREATE TABLE IF NOT EXISTS profile_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    report_type TEXT NOT NULL CHECK (report_type IN ('linkedin', 'github')),
    profile_identifier TEXT NOT NULL,  -- LinkedIn URL or GitHub username
    profile_name TEXT,
    profile_image TEXT,
    overall_score INTEGER NOT NULL DEFAULT 0,
    report_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_profile_reports_user_id ON profile_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_profile_reports_type ON profile_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_profile_reports_created_at ON profile_reports(created_at DESC);

-- RLS Policies
ALTER TABLE profile_reports ENABLE ROW LEVEL SECURITY;

-- Users can only see their own reports
CREATE POLICY "Users can view own reports"
    ON profile_reports FOR SELECT
    USING (auth.uid() = user_id);

-- Users can insert their own reports
CREATE POLICY "Users can insert own reports"
    ON profile_reports FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can delete their own reports
CREATE POLICY "Users can delete own reports"
    ON profile_reports FOR DELETE
    USING (auth.uid() = user_id);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_profile_reports_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_profile_reports_updated_at
    BEFORE UPDATE ON profile_reports
    FOR EACH ROW
    EXECUTE FUNCTION update_profile_reports_updated_at();
