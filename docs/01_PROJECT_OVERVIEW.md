# ResuMax 2.0 — Complete Project Overview

## What is ResuMax?

ResuMax 2.0 is an **AI-powered resume optimizer** built for the CHARUSAT Hackathon 2026. It takes a user's resume and a target job description, then uses a deep AI pipeline to:

1. **Parse** the resume into structured data
2. **Score** it against ATS (Applicant Tracking System) requirements  
3. **Analyze** deep semantic gaps between resume and job requirements
4. **Interview** the user to extract missing achievements/metrics
5. **Rewrite** weak bullet points using STAR format
6. **Optimize** the final resume for maximum ATS score

The flagship feature is **JARVIS** — an interactive AI advisor that talks like Tony Stark's AI assistant, presenting suggestions one at a time and letting the user accept/reject them live.

---

## Frontend Architecture (Already Built)

### Tech Stack
- **Next.js 15** (App Router, TypeScript)
- **Tailwind CSS v4** (CSS-first config)
- **GSAP** (ScrollTrigger, TextPlugin, CustomEase) for all animations
- **Lenis** for smooth scrolling
- **Three.js** for 3D particle background with bloom post-processing
- **Framer Motion** (motion) for component animations
- **Lucide React** for icons

### Design Language
- **Theme**: Cinematic Dark — near-black (#080808) base
- **Typography**: Inter (display/body) + JetBrains Mono (data/labels)
- **Aesthetic**: Glassmorphism, subtle glow effects, no bright colors except score indicators
- **Interaction**: Custom cursor (inner dot + outer ring), GSAP-driven reveals, scroll-pinned sections

### Route Map

| Route | File | Status | Purpose |
|---|---|---|---|
| `/` | `app/page.tsx` | ✅ Complete | Cinematic landing page with 3D scene, scroll-driven sections |
| `/signup` | `app/signup/page.tsx` | ✅ UI Complete | Glassmorphic signup form (needs backend) |
| `/login` | `app/login/page.tsx` | 🔲 Placeholder | Empty dark div (needs full implementation) |
| `/register` | `app/register/page.tsx` | 🔲 Placeholder | Duplicate — should redirect to `/signup` |
| `/analyze` | `app/analyze/page.tsx` | 🔲 Placeholder | Core feature — resume upload + analysis |
| `/dashboard` | `app/dashboard/page.tsx` | 🔲 Placeholder | Analysis results display |
| `/history` | `app/history/page.tsx` | 🔲 Placeholder | Past analyses list |

### Component Tree

```
app/
├── layout.tsx          — Root layout (LenisProvider, CustomCursor, fonts, GSAP init)
├── globals.css         — Full design token system (CSS variables + Tailwind v4 @theme)
├── page.tsx            — Landing page assembly
│
├── signup/page.tsx     — Glassmorphic sign-up form (GSAP animations)
├── login/page.tsx      — Empty (needs building)
├── analyze/page.tsx    — Empty (needs building)
├── dashboard/page.tsx  — Empty (needs building)
├── history/page.tsx    — Empty (needs building)

components/
├── landing/
│   ├── Navbar.tsx              — Fixed bottom nav bar (floating pill shape)
│   ├── HeroSection.tsx         — Character scramble title + ResumePanel
│   ├── ResumePanel.tsx         — Animated resume card with scan line + stats
│   ├── PrecisionPipeline/      — 6-step horizontal scroll pipeline
│   │   ├── index.tsx           — Scroll container + GSAP pin/scrub
│   │   ├── PipelineCard.tsx    — Individual step card
│   │   ├── PipelineNode.tsx    — Circular step indicator
│   │   ├── Connector.tsx       — Animated line between nodes
│   │   └── AIChatPreview.tsx   — Mini chat preview (AI ↔ User)
│   ├── ComponentsSection.tsx   — 4 feature cards (ATS, STAR, Skills, Density)
│   ├── FeedbackSection.tsx     — 3 score rings (28/60/89)
│   ├── OptimizerSection.tsx    — Optimized bullet points preview
│   ├── SiteFooter.tsx          — Minimal footer
│   ├── QuantumCore3D.tsx       — Icosahedron + rings 3D component
│   ├── AtomWireframe3D.tsx     — Atom/orbit wireframe 3D component
│   └── DocumentParticles3D.tsx — Document-shaped particle system
│
├── ui/
│   ├── button.tsx              — shadcn-style Button (4 variants)
│   ├── card.tsx                — shadcn-style Card
│   ├── badge.tsx               — shadcn-style Badge
│   └── CustomCursor.tsx        — Custom cursor (inner dot + lagged ring)
│
├── providers/
│   └── LenisProvider.tsx       — Lenis smooth scroll context
│
└── three/
    ├── SceneCanvas.tsx         — Three.js canvas mount + RAF loop
    ├── SceneConfig.ts          — Scene lights setup
    └── ParticleField.ts        — 200 floating dust particles

lib/
├── gsap-config.ts      — GSAP plugin registration + cinematic eases
├── lenis.ts            — Lenis init + GSAP bridge
├── three-scene.ts      — ThreeScene singleton (scene, camera, renderer, bloom)
└── utils.ts            — cn() utility (clsx + tailwind-merge)

hooks/
├── useIsClient.ts      — SSR safety hook
├── useReducedMotion.ts — prefers-reduced-motion detection
└── useWindowSize.ts    — Window resize hook
```

---

## Backend Requirements (What Frontend Expects)

### Authentication Flow
1. User signs up at `/signup` (full name, email, password)
2. User logs in at `/login` (email, password)
3. JWT token stored client-side (Supabase handles this)
4. All API calls include `Authorization: Bearer <token>`
5. Protected routes redirect to `/login` if not authenticated

### Analysis Flow (What `/analyze` Page Will Do)
1. User uploads resume (PDF/DOCX/TXT) + pastes job description
2. Frontend calls `POST /api/analysis/start` with files
3. Backend starts pipeline, returns `analysis_id`
4. Frontend subscribes to Supabase Realtime channel `analysis:{id}`
5. Backend updates status as each pipeline node completes
6. Frontend shows live progress (6-step pipeline tracker)
7. On completion, redirects to `/dashboard?id={analysis_id}`

### Dashboard Data (What `/dashboard` Needs)
- ATS Score (0-100) with breakdown
- Keyword matches (list of matched/missing with importance)
- Skill analysis (matched/gaps/implicit)
- Bullet rewrites (before/after pairs)
- Deep analysis summary (strengths/weaknesses)
- Density analysis metrics
- "Talk to JARVIS" button → opens interactive advisor

### History Data (What `/history` Needs)
- List of past analyses with:
  - Date, job title
  - ATS score
  - Status (completed/failed)
  - Link to view full results

### JARVIS Data (Interactive Advisor)
- WebSocket connection for real-time chat
- Messages stream in with typing indicator
- Suggestion cards with accept/reject buttons
- Live score updates as changes are applied
- Session summary at the end

---

## Design Tokens Reference

```css
/* Backgrounds */
#080808  — Page base (resumax-950)
#111111  — Card surface (resumax-900)
#1a1a1a  — Elevated surface (resumax-800)
#222222  — Overlay (resumax-700)

/* Text */
#FFFFFF  — Primary (headings, CTAs)
#AAAAAA  — Secondary (body text)
#666666  — Muted (labels, placeholders)
#333333  — Disabled

/* Borders */
#1e1e1e  — Subtle (card borders)
#2a2a2a  — Default (active cards)
#3d3d3d  — Strong (hover/focus)

/* Accent Colors */
#4a9eff  — Glow blue (cube glow, interactive elements)
#ff4444  — Score low (<40)
#ffaa00  — Score mid (40-70)
#ffffff  — Score high (70+)

/* Emerald (auth pages) */
emerald-500  — Primary action buttons
emerald-400  — Hover state
```

---

## Key Design Principles for Backend Pages

1. **Dark theme always** — bg is always #080808, cards are #0a0a0a or #111111
2. **Glassmorphism** — Use `bg-white/[0.03] backdrop-blur-2xl border-white/10`
3. **GSAP for animations** — Using `import { gsap } from '@/lib/gsap-config'`
4. **Mono labels** — Small labels use `font-mono text-xs tracking-widest uppercase text-[#888]`
5. **Score colors** — Red (#ff4444) < 40, Orange (#ffaa00) 40-70, White (#ffffff) 70+
6. **Bottom navbar** — Navbar is fixed at bottom, z-100, floating pill shape
7. **No bright colors** — Everything is monochrome except for score indicators and emerald CTAs
