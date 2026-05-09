# Pitchcraft

AI-powered proposal automation platform for PR/marketing agency Account teams. From a client brief to a presentation-ready PowerPoint deck in under 30 minutes — with human oversight at every critical decision.

## Why Pitchcraft

Account teams at agencies spend 3–5 days per pitch doing work that is largely repeatable: competitor research, strategy frameworks, deck structuring, KOL matching, content writing. Pitchcraft compresses this to under 30 minutes by automating the repeatable parts while keeping humans in the loop for judgment calls and client relationship decisions.

**Target users:** Account / Lead Account / Admin roles at PR, advertising, and integrated marketing agencies.

---

## Product Features

### Multi-Agent Pipeline

Six specialized AI agents orchestrated in a stateful LangGraph pipeline:

```
Brief Input
    │
    ▼
┌─────────────────┐
│  Brief Analyzer  │ ← Node 1: HITL confirm interpretation
└────────┬────────┘
         │
    ┌────┴────┐        (fan-out parallel)
    ▼         ▼
┌────────┐ ┌──────────────┐
│Research│ │Strategy Ph.1 │
└───┬────┘ └──────┬───────┘
    │              │       (fan-in)
    ▼              ▼
┌──────────────────────┐
│   Strategy Phase 2    │ ← Node 2: HITL confirm strategy
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│    Resource Agent      │   (conditional: skips if not needed)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Deck Orchestrator   │ ← Node 3: HITL confirm structure
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Slide Content Agent   │   (streaming: push each slide to frontend)
│ + Narrative Agent     │   (non-blocking coherence check)
└──────────┬───────────┘
           │              ← Node 4: Gallery Review (batch regenerate)
           ▼
┌──────────────────────┐
│     PPT Builder       │ → .pptx download
└──────────────────────┘
           │              ← Node 5: Client feedback → targeted rerun
```

### Agent Capabilities

| Agent | What It Does |
|-------|-------------|
| **Brief Analyzer** | Parses free-text briefs → structured fields (client, theme, audience, channels, budget, timeline). Detects missing fields and generates clarification questions. |
| **Research Agent** | Web search (Tavily → DuckDuckGo fallback) + internal history RAG + social data APIs (Chanmama/Feigua for CN, CreatorIQ for global) + multimodal competitor screenshot analysis via Claude Vision. |
| **Strategy Agent** | Two-phase: Phase 1 (audience insights, brand direction) runs parallel with research. Phase 2 (Big Idea, communication logic, channel mix, budget allocation, KPIs) integrates research results. Outputs structured JSON consumed by downstream agents. |
| **Resource Agent** | Multi-type matching: KOL/KOC, media outlets, vendors (event/production), ad placements (OOH/elevator/cinema). Auto-detects needed types from strategy output. Skips entirely when no external resources needed. |
| **Deck System** | Orchestrator plans structure (three-tier priority: global → client → project templates). Content Agent generates per-slide copy with brand tone from RAG. Narrative Agent provides page-referenced coherence suggestions. |
| **PPT Builder** | Template-based assembly via python-pptx. 5 templates (social, PR, integrated, brand_refresh, default). Web preview + .pptx download. |

### Human-in-the-Loop (HITL)

Five pause points where the pipeline stops and waits for human confirmation via WebSocket push:

| Node | Decision | Rerun Options |
|------|----------|---------------|
| 1 | Confirm brief interpretation | — |
| 2 | Confirm strategy direction | Refresh research / rerun strategy only / both |
| 3 | Confirm or edit slide structure | Add / remove / reorder slides |
| 4 | Gallery Review: browse all slides | Mark pages for batch regeneration |
| 5 | Record client feedback | Targeted rerun from any upstream node |

### Client Feedback Loop

- Approved directions are embedded into the Brand Library (Pinecone `brand_spec` namespace) for future pipeline runs
- Rejected directions are injected as constraints in Strategy Phase 2 to prevent repetition
- System auto-suggests which node to rerun based on feedback target (strategy / structure / slide / resource)
- Supports partial pipeline re-execution via `start_from` parameter

### RAG & Knowledge System

- **Brand Library** (per-client): brand specs, historical proposals, brand copy → Pinecone `brand_spec_{client_id}` and `brand_history_{client_id}`
- **Project Library** (per-project): project briefs, competitor materials → Pinecone `project_{project_id}`
- **Resource Library** (per-client): KOL, media, vendor, placement databases → type-specific Pinecone namespaces
- **Visual Reference Processing**: PPTX/PDF → page-level PNG rendering (LibreOffice headless) → Claude Vision style extraction (colors, layout, typography, density) → text embedding for RAG retrieval
- **Semantic chunking**: token-based splitting on paragraph/sentence boundaries, language-agnostic
- **BGE-M3 embedding**: self-hosted, multilingual (Chinese + English), zero API cost

### Multilingual Support

- Auto-detects brief language (Chinese / English) and selects matching prompt templates
- Locale-aware research: CN briefs trigger Chanmama (Douyin) + Feigua (Xiaohongshu); global briefs use CreatorIQ
- BGE-M3 handles mixed-language embeddings natively

### Stability & Guardrails

- **Request Budget**: max 30 LLM calls, 10 search calls, 300s timeout per pipeline run
- **Fallback Chains**: Tavily → DuckDuckGo → internal-only; each external dependency has deterministic fallback
- **Semantic Cache**: Redis-backed, 30-day TTL, keyed by `client_id:competitor:date_bucket`
- **Per-stage metrics**: timing, token usage, success/failure tracked in MongoDB `stage_metrics` collection

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Client (Browser)                            │
│   Next.js 14 · TypeScript · WebSocket (real-time pipeline updates)   │
└─────────────────────────┬──────────────────────────┬────────────────┘
                          │ HTTP/REST                 │ WebSocket
                          ▼                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           Nginx (Reverse Proxy)                       │
└─────────────────────────┬──────────────────────────┬────────────────┘
                          │                          │
                          ▼                          ▼
┌──────────────────────────────────────┐  ┌────────────────────────────┐
│         FastAPI Backend               │  │   WebSocket Server          │
│  • REST API (auth, files, pipeline)   │  │   • Pipeline status push    │
│  • JWT auth (Google/MS OAuth + email) │  │   • HITL event delivery     │
│  • Task dispatch to Celery            │  │   • Slide streaming          │
└─────────────┬────────────────────────┘  └────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│          Celery Workers               │
│  • PipelineExecutor (LangGraph)       │
│  • Visual file processing (600s TL)   │
│  • Feedback embedding                 │
└──┬────────────┬──────────┬───────────┘
   │            │          │
   ▼            ▼          ▼
┌───────┐  ┌────────┐  ┌───────────────────┐
│ Redis  │  │MongoDB │  │   Pinecone         │
│ broker │  │ Atlas  │  │   (vector store)   │
│ + cache│  │        │  │   namespace-isolated│
└───────┘  └────────┘  └───────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  BGE-M3 Service   │
                    │  (self-hosted)    │
                    └──────────────────┘
```

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS | App Router, WebSocket hooks, Gallery Review UI |
| Backend API | FastAPI, Pydantic | REST endpoints, JWT auth, request validation |
| Task Queue | Celery + Redis | Async pipeline execution, visual processing |
| Agent Orchestration | LangGraph | Fan-out/fan-in parallelism, HITL pauses, conditional branching |
| LLM | Claude (Anthropic) | Strategy generation, content writing, visual analysis |
| Vector Store | Pinecone | Namespace-isolated RAG (brand, project, resource) |
| Embedding | BGE-M3 (self-hosted) | Multilingual dense+sparse embeddings |
| Database | MongoDB | Multi-tenant data (orgs, users, clients, projects, proposals) |
| Cache | Redis | Semantic research cache (30-day TTL), pub/sub for WebSocket |
| PPT Generation | python-pptx | Template-based slide assembly |
| Visual Processing | LibreOffice headless + pdftoppm | PPTX/PDF → PNG rendering for style analysis |
| Auth | Google OAuth, Microsoft OAuth, JWT | Multi-provider SSO + email/password fallback |
| Container | Docker Compose (8 services) | Backend, frontend, worker, Redis, MongoDB, Nginx, BGE-M3, Pinecone |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Structured JSON data contracts between agents | Downstream agents read explicit fields (`channels[]`, `resource_types[]`, `budget_allocation{}`) instead of keyword-guessing from prose text |
| Research ‖ Strategy Phase 1 parallelism | LangGraph fan-out/fan-in saves ~8s per run; Phase 2 waits for both to complete |
| BGE-M3 over OpenAI text-embedding-3-small | Superior multilingual (CN+EN) marketing terminology; open-source, self-hosted, zero per-call cost |
| Narrative Agent as non-blocking advisor | No flow control or retry loops — suggestions displayed alongside slides in Gallery Review |
| Namespace-isolated Pinecone | Client/project/resource data never leaks across tenants; enables per-client brand learning |
| Feedback embeds to brand namespace | System learns approved directions over time, improving strategy quality per-client |
| Token-based semantic chunking | Language-agnostic paragraph/sentence boundary splitting; handles mixed CN/EN documents |
| Soft-delete for files | Running pipelines unaffected when teammates modify shared Brand Library |
| Visual style → text embedding | Claude Vision extracts style JSON → text description → BGE-M3 embedding; enables RAG retrieval of visual identity |

---

## Multi-Tenancy Model

```
Organization (Agency)
  └── Users: account / lead_account / admin
       └── Clients (shared across org)
            ├── Brand Library (brand specs, history, visual refs)
            ├── Resource Library (KOLs, media, vendors, placements)
            └── Projects
                 └── Proposals (pipeline runs, versions, feedback)
```

- Organization context derived from JWT (no org-switching UI needed)
- Role-based permissions: account (own projects), lead_account (team projects), admin (org-wide)
- Brand Library shared at client level; all accounts in the org contribute and benefit

---

## Project Structure

```
pitchcraft/
├── backend/
│   ├── api/v1/endpoints/         # REST endpoints (auth, files, pipeline, resources, research, proposals)
│   ├── core/
│   │   ├── agents/               # brief.py, research.py, strategy.py, resource.py, deck.py,
│   │   │                         # social_data.py, visual_analysis.py
│   │   ├── graph/                # pipeline.py (LangGraph nodes), executor.py (run/rerun),
│   │   │                         # state.py (PipelineState)
│   │   ├── rag/                  # indexer.py, retriever.py, cache.py, resource_import.py,
│   │   │                         # visual_renderer.py, visual_style.py, visual_process.py,
│   │   │                         # feedback_embedder.py
│   │   ├── language/             # router.py (language detection), prompts.py (CN/EN templates)
│   │   ├── stability/            # budget.py (RequestBudget), fallback.py (FallbackChain)
│   │   ├── models/               # resource.py, feedback.py, pipeline.py
│   │   └── database/             # connection.py, repositories (mongo collections)
│   ├── tests/                    # 93 unit tests (pure logic, mocked deps)
│   └── Dockerfile                # Python 3.11 + LibreOffice headless + poppler-utils
├── frontend/
│   ├── app/                      # Next.js App Router pages
│   │   ├── pipeline/             # Pipeline execution + HITL confirmation UIs
│   │   ├── proposals/[id]/       # Proposal detail + FeedbackPanel
│   │   ├── clients/              # Client management
│   │   ├── files/                # File library (upload, visual ref thumbnails)
│   │   ├── resources/            # Resource library (list, filter, Excel import)
│   │   └── research/             # Research data display + refresh
│   ├── components/
│   │   ├── gallery/              # GalleryView, SlideThumbnail, SlidePreview, NarrativePanel
│   │   ├── hitl/                 # HITL confirmation components (Nodes 1-4)
│   │   ├── feedback/             # FeedbackPanel (Node 5)
│   │   ├── pipeline/             # Pipeline execution status view
│   │   └── layout/               # Nav, shell
│   ├── hooks/                    # useWebSocket, usePipeline
│   └── lib/                      # api.ts (HTTP client), ws.ts (WebSocket)
├── infrastructure/
│   └── docker/
│       └── docker-compose.yml    # 8 services: backend, frontend, worker, redis, mongo, nginx, bge-m3, pinecone
├── scripts/
│   └── generate_templates.py     # PPT template generator (5 types)
├── .github/workflows/ci.yml      # pytest + lint + frontend build (3 parallel jobs)
├── docs/dev-notes/               # Development notes and issue tracking
├── PRD.md                        # Product requirements document
├── Architecture.md               # Technical architecture spec
└── ROADMAP.md                    # Phased development plan
```

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.11+

### Environment Variables

```bash
# backend/.env
ANTHROPIC_API_KEY=sk-ant-...        # Claude API
PINECONE_API_KEY=...                 # Vector store
TAVILY_API_KEY=tvly-...              # Web search
GOOGLE_CLIENT_ID=...                 # OAuth
GOOGLE_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
MONGODB_URI=mongodb://...
REDIS_URL=redis://localhost:6379
JWT_SECRET=...
```

### Run

```bash
# Start all services
docker compose up -d

# Backend API:  http://localhost:8000
# Frontend:     http://localhost:3000
# API docs:     http://localhost:8000/docs
```

### Development

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn api.main:app --reload

# Frontend
cd frontend && npm install && npm run dev

# Tests
cd backend && pytest tests/ -v
```

---

## Current Status

**Phase 1 (Core Pipeline)** — Complete. End-to-end flow from brief to PPT download with all 5 HITL checkpoints.

**Phase 2 (Research & Resource Enhancement)** — Complete. Multimodal research, multi-type resources, client feedback loop, visual reference processing.

**Phase 3 (Production Hardening)** — In progress. Version management, analytics dashboard, deployment infrastructure.

See [ROADMAP.md](./ROADMAP.md) for detailed progress.

---

## Documentation

- [PRD](./PRD.md) — Product requirements, user journey, feature specs
- [Architecture](./Architecture.md) — Technical design, data models, API specs
- [Roadmap](./ROADMAP.md) — Phased development plan
- [Dev Notes](./docs/dev-notes/) — Development issues and solutions

## License

Proprietary. All rights reserved.
