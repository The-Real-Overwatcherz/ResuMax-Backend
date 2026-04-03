# ResuMax — Dependencies & Setup Guide

## Python Backend Dependencies

### requirements.txt
```
# Web Framework
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-multipart==0.0.12

# LangChain + LangGraph
langchain==0.3.12
langchain-groq==0.2.4
langchain-aws==0.2.12          # AWS Bedrock integration
langchain-core==0.3.25
langgraph==0.2.56

# Groq SDK (for Whisper + direct access)
groq==0.14.0

# AWS Bedrock
boto3==1.35.0                   # AWS SDK for Bedrock access
botocore==1.35.0                # boto3 core dependency

# Supabase
supabase==2.10.0

# PDF/Document Processing
PyMuPDF==1.24.0          # pip install PyMuPDF (imports as fitz)
python-docx==1.1.0       # DOCX parsing
python-pptx==1.0.0       # Optional: PPT parsing

# Data Validation
pydantic==2.10.0

# Text Processing
tiktoken==0.8.0          # Token counting
unstructured==0.16.0     # Advanced document parsing (optional)

# Voice (Stretch Goal)
edge-tts==6.1.0          # Microsoft Edge TTS (free, no API key)

# Utilities
python-dotenv==1.0.0
httpx==0.27.0            # Async HTTP client
tenacity==9.0.0          # Retry logic
structlog==24.1.0        # Structured logging

# Development
pytest==8.0.0
pytest-asyncio==0.24.0
```

### Installation
```bash
cd ResumaxBackend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt
```

---

## Frontend Additional Dependencies

### Install Supabase client
```bash
cd ResumaxFrontend
npm install @supabase/supabase-js
```

No other frontend dependencies needed — the existing Next.js + Tailwind + GSAP stack handles everything.

---

## Supabase Project Setup

### 1. Create Supabase Project
1. Go to [supabase.com](https://supabase.com) → Sign up / Log in
2. Create new project (free plan)
3. Choose region closest to you
4. Set database password (save it!)
5. Wait for project to provision (~2 minutes)

### 2. Get Credentials
From Supabase Dashboard → Settings → API:
- `Project URL` → `SUPABASE_URL`
- `anon public` key → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (⚠️ backend only, never expose to frontend)

### 3. Run Database Migrations
Go to Supabase Dashboard → SQL Editor → New Query:
Paste and run the full schema from `docs/02_SUPABASE_ARCHITECTURE.md`.

### 4. Configure Storage
Go to Dashboard → Storage:
1. Create bucket: `resumax-resumes`
2. Set to **private** (not public)
3. Add file size limit: 10MB
4. Allowed MIME types: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain`

### 5. Configure Auth
Go to Dashboard → Authentication → Settings:
1. Enable Email Auth (enabled by default)
2. Disable email confirmation for development (or enable for production)
3. Set password minimum length: 6 characters

---

## AWS Bedrock Setup ($200 Free Credits)

### 1. Create AWS Account (NEW — to get credits)
1. Go to [aws.amazon.com](https://aws.amazon.com) → Create a **new** AWS account
2. Choose **"Free account plan"** during signup
3. You'll get **$100 sign-up credits** automatically
4. Complete guided activities in the console for up to **$100 more** (one activity uses the Bedrock playground)
5. Total: **$200 in credits**, valid for **6 months**

> ⚠️ **IMPORTANT**: Set a **$10 AWS Budget Alert** immediately. Go to AWS Billing → Budgets → Create Budget. This prevents accidental overcharges if you misconfigure something.

### 2. Enable Bedrock Model Access
1. Go to AWS Console → Amazon Bedrock → Model access
2. Request access to:
   - **Anthropic Claude 3.5 Haiku** (primary deep model)
   - **Amazon Nova Micro** (cheap fallback)
   - **Amazon Titan Text Embeddings v2** (for semantic skill matching)
3. Access is typically granted instantly for these models

### 3. Create IAM Access Keys
1. Go to IAM → Users → Create User (e.g., `resumax-backend`)
2. Attach policy: `AmazonBedrockFullAccess`
3. Create Access Key → Save `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
4. Set region to `us-east-1` (best model availability)

### 4. Verify Setup
```bash
pip install boto3
python -c "
import boto3
client = boto3.client('bedrock-runtime', region_name='us-east-1')
print('Bedrock connected successfully!')
"

---

## Groq API Setup

### 1. Get API Key
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up (email or GitHub, no credit card)
3. Go to API Keys → Create New Key
4. Copy key → `GROQ_API_KEY`

### 2. Check Rate Limits
Go to Settings → Limits to see your specific limits:
- Llama 3.3 70B: ~30 RPM, ~1000 RPD
- Llama 3.1 8B: ~30 RPM, ~14,400 RPD
- Whisper: ~2000 RPD

---

## Environment Files

### Backend `.env`
```env
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...

# Groq (free tier)
GROQ_API_KEY=gsk_xxxxx

# AWS Bedrock ($200 credits)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=xxxxx
AWS_REGION=us-east-1

# Server
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:3000

# Optional
LOG_LEVEL=INFO
```

### Frontend `.env.local`
```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGci...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Running Locally

### Terminal 1: Backend
```bash
cd ResumaxBackend
venv\Scripts\activate     # Windows
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2: Frontend
```bash
cd ResumaxFrontend
npm run dev
```

### Access
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs

---

## Project File Structure (Complete)

```
ResuMax/
├── ResumaxFrontend/          # Next.js 15 frontend (EXISTING)
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   ├── styles/
│   ├── public/
│   └── package.json
│
├── ResumaxBackend/           # Python FastAPI backend (NEW)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app entry point
│   │   ├── config.py         # Environment config
│   │   ├── api/              # REST + WebSocket routes
│   │   │   ├── auth.py
│   │   │   ├── analysis.py
│   │   │   ├── history.py
│   │   │   ├── jarvis.py
│   │   │   └── export.py
│   │   ├── pipeline/         # LangGraph pipeline
│   │   │   ├── graph.py      # Main graph definition
│   │   │   ├── state.py      # PipelineState TypedDict
│   │   │   ├── nodes/        # 8 pipeline nodes
│   │   │   ├── prompts/      # LLM prompt templates
│   │   │   └── chains/       # LCEL chains
│   │   ├── jarvis/           # JARVIS advisor engine
│   │   │   ├── engine.py
│   │   │   ├── suggestions.py
│   │   │   ├── personality.py
│   │   │   └── voice.py
│   │   ├── services/         # External integrations
│   │   │   ├── supabase.py
│   │   │   ├── groq_client.py
│   │   │   ├── file_parser.py
│   │   │   └── export_service.py
│   │   ├── models/           # Pydantic models
│   │   │   ├── resume.py
│   │   │   ├── analysis.py
│   │   │   ├── jarvis.py
│   │   │   └── api.py
│   │   └── utils/
│   │       ├── text_processing.py
│   │       └── scoring.py
│   ├── tests/
│   │   ├── test_parser.py
│   │   ├── test_ats_scorer.py
│   │   ├── test_full_pipeline.py
│   │   └── test_jarvis.py
│   ├── docs/                 # Architecture documentation
│   │   ├── 01_PROJECT_OVERVIEW.md
│   │   ├── 02_SUPABASE_ARCHITECTURE.md
│   │   ├── 03_PIPELINE_SPECIFICATION.md
│   │   ├── 04_JARVIS_SPECIFICATION.md
│   │   ├── 05_API_SPECIFICATION.md
│   │   └── 06_SETUP_AND_DEPENDENCIES.md
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   └── README.md
│
└── test assets/              # Test files (EXISTING)
    ├── *.png
    └── *.mp4
```
