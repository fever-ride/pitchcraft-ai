# Pitchcraft

AI-powered proposal automation platform for PR/marketing agency Account teams. From a client brief to a presentation-ready PowerPoint deck in under 30 minutes — with human oversight at every critical decision.

## Why Pitchcraft

Account teams at agencies spend 3–5 days per pitch doing work that is largely repeatable: competitor research, strategy frameworks, deck structuring, KOL matching, content writing. Pitchcraft compresses this to under 30 minutes by automating the repeatable parts while keeping humans in the loop for judgment calls and client relationship decisions.

**Target users:** Account / Lead Account / Admin roles at PR, advertising, and integrated marketing agencies.

---

## Product Features

### Multi-Agent Pipeline

Six specialized AI agents orchestrated via LangGraph with **parallel execution**, **conditional branching**, **5 HITL checkpoints**, and **feedback-driven rerun** from any upstream node:

```
Brief Input
    │
    ▼
┌─────────────────┐
│  Brief Analyzer  │ ← HITL Node 1: confirm/edit interpretation
└────────┬────────┘
         │
    ┌────┴────┐           ┌───────────────────────────────────────────┐
    ▼         ▼           │  LangGraph fan-out: two agents run        │
┌────────┐ ┌───────────┐ │  concurrently via asyncio.gather().       │
│Research│ │Strategy P1 │ │  P1 uses only Brief + Brand Library;      │
│  Agent │ │(no research│ │  Research uses web + internal RAG.        │
│        │ │  needed)   │ │  Fan-in barrier: both must finish before  │
└───┬────┘ └─────┬─────┘ │  Phase 2 can start.                       │
    │            │        └───────────────────────────────────────────┘
    └─────┬──────┘
          ▼
┌──────────────────────┐  ┌───────────────────────────────────────────┐
│  Strategy Phase 2     │  │  Receives: research_result + phase1_insight│
│  + Brand Check        │  │  Reads: rejected directions from feedback  │
└──────────┬───────────┘  │  Output: StrategyPhase2Result (Pydantic,    │
           │              │  enforced via tool_use structured output)   │
           │  ← HITL Node 2  → big_idea, channels[], resource_types[], │
           │              │    budget_allocation{}, kpis[], timeline[]  │
           │              └───────────────────────────────────────────┘
           ▼
┌──────────────────────┐  ┌───────────────────────────────────────────┐
│   Resource Agent      │  │  CONDITIONAL: reads state["resource_types_ │
│                       │  │  needed"] (typed list from Strategy P2).    │
│  (may skip entirely)  │  │  If empty → clean skip, zero LLM calls.    │
└──────────┬───────────┘  │  If multiple types → parallel Pinecone      │
           │              │  queries across namespaces.                  │
           │              └───────────────────────────────────────────┘
           ▼
┌──────────────────────┐  ← HITL Node 3: confirm/edit structure
│  Deck Orchestrator    │  (three-tier lookup: project → client → LLM)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐  ┌───────────────────────────────────────────┐
│ Slide Content Agent   │  │  Streaming: each completed slide pushed   │
│                       │  │  to frontend via WebSocket immediately.    │
│ Narrative Agent ──────│──│─ Runs NON-BLOCKING in parallel with       │
│ (coherence advisor)   │  │  slide generation. Outputs suggestions    │
└──────────┬───────────┘  │  with page references, never blocks flow.  │
           │              └───────────────────────────────────────────┘
           │  ← HITL Node 4: Gallery Review (batch mark + regenerate)
           ▼
┌──────────────────────┐
│     PPT Builder       │ → .pptx download + web preview
└──────────┬───────────┘
           │
           │  ← HITL Node 5: Client feedback
           │
           │    ┌──────────────────────────────────────────────────┐
           └───▶│  FEEDBACK-DRIVEN RERUN                            │
                │                                                    │
                │  Client says "strategy direction is wrong"         │
                │       → system suggests: rerun from Strategy P2    │
                │  Client says "slide 7 content is off-brand"        │
                │       → system suggests: rerun from Slide Content  │
                │  Client says "wrong KOL selection"                 │
                │       → system suggests: rerun from Resource Agent │
                │                                                    │
                │  Executor receives start_from="strategy_phase2"    │
                │  and re-executes from that node forward,           │
                │  preserving all upstream state.                    │
                │                                                    │
                │  Each rerun auto-saves a new VERSION SNAPSHOT.     │
                └─────────────────────┬────────────────────────────┘
                                      │
                                      ▼ (pipeline resumes from target node)
```

### Pipeline Orchestration Details

**1. Parallel Execution with Data Dependencies**
- Research Agent and Strategy Phase 1 run concurrently (`asyncio.gather`) — neither depends on the other
- Strategy Phase 2 **cannot start** until both complete (fan-in barrier)
- Narrative Agent runs in parallel with Slide Content Agent but is purely advisory (no flow control)

**2. Conditional Branching**
- Resource Agent reads `state["resource_types_needed"]` (typed `list[str]`, written by Strategy Phase 2 node) to determine which resource types to retrieve
- When `resource_types_needed = ["kol", "media"]` → Resource Agent queries `resource_kol` and `resource_media` namespaces in parallel
- When `resource_types_needed = []` → Resource Agent skips entirely (zero latency, zero LLM cost)
- Deck Orchestrator uses three-tier template lookup: if project has a saved structure → use it; else if client has a default → use it; else generate via LLM

**3. Stateful HITL Pause/Resume**
- Pipeline state is checkpointed to **Redis** before every node and at every HITL pause
- On HITL pause, the executor publishes a WebSocket event and blocks on Redis pub/sub (`wait_for_resume`)
- Frontend receives the event, renders the confirmation UI, user responds → Redis publish → executor unblocks
- If the user takes 3 hours to respond, the state survives (24h TTL)
- The pipeline is a **Celery task** — the WebSocket server and the executor are different processes communicating via Redis

**4. Feedback-Driven Partial Rerun (Non-Linear Control Flow)**

The most architecturally interesting piece. After pipeline completion:

```python
RERUN_SUGGESTIONS = {
    FeedbackTarget.STRATEGY:  "strategy_phase2",    # re-derive Big Idea + channels
    FeedbackTarget.STRUCTURE: "deck_orchestrator",  # re-plan slide structure
    FeedbackTarget.SLIDE:     "slide_content",      # regenerate slide copy
    FeedbackTarget.RESOURCE:  "resource_agent",     # re-match resources
    FeedbackTarget.OVERALL:   "parallel_research_strategy",  # full redo
}
```

When client feedback triggers a rerun:
- Executor skips all nodes before `start_from` in the `node_sequence`
- Upstream state (brief, research, etc.) is preserved from Redis
- Only downstream nodes re-execute
- **Rejected directions** from feedback are injected as constraints into Strategy Phase 2's prompt, preventing the system from repeating mistakes
- **Approved directions** are embedded into the brand_spec Pinecone namespace, improving future runs for this client

This creates a **non-linear DAG** where the pipeline can jump back to any node while preserving partial results — not just a linear retry.

**5. Inter-Agent Communication: Tool-Use Structured Output + Typed State**

Agents produce structured output via **Anthropic tool_use** (forced function calling), not prompt-based JSON extraction. Each agent's output is defined as a Pydantic schema and enforced at the LLM call level (~99% format compliance vs ~90% for prompt-instructed JSON).

```python
# Each agent has a Pydantic schema (backend/core/agents/schemas.py)
class StrategyPhase2Result(BaseModel):
    big_idea: str
    channels: list[Channel]
    resource_types: list[str]  # ["kol", "media", "vendor", "placement"]
    budget_allocation: dict[str, str]
    kpis: list[str]
    timeline_phases: list[TimelinePhase]

# LLM is invoked with schema enforcement (tool_use under the hood)
result = await invoke_llm_structured(messages, output_schema=StrategyPhase2Result)
```

Pipeline nodes write **specific typed fields** to LangGraph state. Downstream agents read only the fields they need — no `json.dumps(full_upstream_dict)` passing:

```
State after Strategy Phase 2:
  state["big_idea"] = "..."          ← Deck Orchestrator reads this
  state["channels"] = [...]          ← Resource Agent + Deck reads this
  state["resource_types_needed"] = ["kol", "media"]  ← Resource Agent reads this directly
  state["kpis"] = [...]              ← Deck Orchestrator reads this
```

- Resource Agent receives `big_idea`, `channels`, `resource_types_needed` as explicit parameters — zero re-detection logic
- Deck Orchestrator receives `big_idea`, `channels`, `kpis` — not a full strategy blob
- Slide Content Agent receives `big_idea` + `brand_direction` — only what it needs for copywriting
- Brand Check receives strategy text for semantic comparison against brand_spec RAG

This eliminates: (1) fragile keyword-matching fallbacks, (2) JSON parse failures from malformed LLM output, (3) information over-sharing between agents.

**6. Version Snapshots and Rollback**

Every pipeline completion (initial or rerun) triggers an automatic version save:
- Full state snapshot stored in MongoDB `proposal_versions` collection
- Versions are immutable — rollback creates a **new** version from an old snapshot
- Diff API compares any two versions field-by-field
- Frontend shows version timeline with trigger labels (Initial / Rerun / Rollback)

### Agent Capabilities

| Agent | Inputs | Outputs | Key Behaviors |
|-------|--------|---------|---------------|
| **Brief Analyzer** | Raw text brief | `structured_brief{}` | Extracts fields (client, theme, audience, channels, budget, timeline, objective). Detects missing fields → generates clarification questions. |
| **Research Agent** | `structured_brief`, `client_id` | `research_result{}` | Web search (Tavily → DuckDuckGo fallback) + internal RAG + social data APIs (locale-aware: CN → Chanmama/Feigua, Global → CreatorIQ) + multimodal competitor screenshots via Claude Vision. Cached 30 days. |
| **Strategy P1** | `structured_brief`, brand_spec RAG | `strategy_insight{}` | Audience segments, brand direction, emotional hooks. Runs **without** waiting for research. |
| **Strategy P2** | `research_result` + `strategy_insight` + rejected directions | `strategy_result{}` (JSON contract) | Big Idea, communication logic, channels, resource_types, budget_allocation, KPIs, timeline. Avoids previously rejected directions. |
| **Resource Agent** | `state["resource_types_needed"]`, `state["channels"]`, `state["big_idea"]` | `ResourceResult` (Pydantic) | Reads typed fields directly from state — no re-detection. Multi-type parallel retrieval (KOL/KOC, media, vendor, placement). Conditional skip when `resource_types_needed` is empty. |
| **Deck System** | `strategy_result`, `resource_result`, brand RAG | `deck_structure[]`, `slides[]`, `narrative_suggestions[]` | Orchestrator: three-tier template lookup. Content Agent: per-slide generation with brand tone. Narrative Agent: non-blocking coherence check with page refs. |
| **PPT Builder** | `slides[]`, template | `pptx_path` | python-pptx assembly. 5 templates (social, PR, integrated, brand_refresh, default). |

### Human-in-the-Loop (HITL)

Five pause points. Each one: executor checkpoints state → publishes WebSocket event → blocks on Redis pub/sub → user responds → executor resumes.

| Node | What the User Sees | What They Can Do | What Happens Next |
|------|-------------------|------------------|-------------------|
| 1 | Parsed brief fields + clarification questions | Confirm / edit fields | Pipeline continues to parallel phase |
| 2 | Strategy result + research summary + brand check status | Confirm / reject / request research refresh | If rejected: re-executes strategy with feedback. If refresh: re-runs research first. |
| 3 | Proposed slide structure (titles, ordering) | Add / remove / reorder slides | Deck generation uses modified structure |
| 4 | Full slide gallery + narrative suggestions panel | Mark slides for regeneration (batch) | Flagged slides re-generated, others preserved |
| 5 | Final proposal + feedback form | Tag feedback target + directions | Triggers targeted rerun from appropriate node |

### Client Feedback Loop (Learning System)

Not just a one-shot rerun — the system **learns** from client feedback:

```
Feedback submitted
    │
    ├─ approved_directions[] ──▶ Embed into brand_spec_{client_id} namespace
    │                            (available to ALL future pipeline runs for this client)
    │
    ├─ rejected_directions[] ──▶ Stored in feedback collection
    │                            (injected as constraints next time Strategy P2 runs)
    │
    └─ trigger_rerun ──────────▶ RERUN_SUGGESTIONS[target] → start_from node
                                  (executor skips upstream, re-runs downstream)
```

Over multiple proposals for the same client, the system accumulates brand knowledge:
- Strategy outputs improve (avoids rejected directions, aligns with approved ones)
- Brand tone becomes more consistent (approved directions in RAG context)
- Resource matching improves (feedback on KOL/media selections refines future queries)

### RAG & Knowledge System

- **Brand Library** (per-client): brand specs, historical proposals, brand copy → Pinecone `brand_spec_{client_id}` and `brand_history_{client_id}`
- **Project Library** (per-project): project briefs, competitor materials → Pinecone `project_{project_id}`
- **Resource Library** (per-client): KOL, media, vendor, placement databases → type-specific Pinecone namespaces
- **Visual Reference Processing**: PPTX/PDF → page-level PNG rendering (LibreOffice headless) → Claude Vision style extraction (colors, layout, typography, density) → text embedding for RAG retrieval
- **Semantic chunking**: token-based splitting on paragraph/sentence boundaries, language-agnostic
- **BGE-M3 embedding**: self-hosted, multilingual (Chinese + English), zero API cost

### Multilingual Support

The pipeline separates "comprehension language" from "output language" as two independent dimensions:

```
┌─────────────────────────────────────────────────────────────┐
│  input_language (auto-detected)                             │
│  Used by: Brief Analyzer, Strategy P1/P2                    │
│  Source: detect_language(brief) → "zh" or "en"             │
│  Purpose: select the prompt template that best understands  │
│           the user's input                                  │
├─────────────────────────────────────────────────────────────┤
│  output_language (user-specified, default: auto)            │
│  Used by: Deck Orchestrator, Slide Content, Narrative Agent │
│  Source: user selects at pipeline start (zh / en / auto)    │
│  Purpose: control the language of the final deliverable     │
└─────────────────────────────────────────────────────────────┘

Typical scenario: Chinese brief → Chinese strategy (internal HITL review)
               → English PPT (client deliverable)
```

**Technology choices:**

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Embedding | BGE-M3 (self-hosted) | Best-in-class for mixed CN/EN marketing terminology retrieval; open-source, zero API cost; outputs dense + sparse vectors simultaneously |
| LLM | Claude (Anthropic) | Strong bilingual (CN+EN) capability; reliable JSON structured output; Vision support for competitor screenshot analysis |
| Language detection | langdetect | Lightweight, pure Python, sufficient accuracy for paragraph-level text |
| Prompt templates | Dual CN/EN per agent | Same JSON schema for both languages — only instruction language differs, downstream parsing unaffected |

**Implementation details:**

- Mixed-language briefs (Chinese text with English brand names, channel names, KPI terms) are handled naturally — `detect_language` picks the dominant language for prompt selection, the LLM understands mixed input regardless
- Locale-aware data sources: CN briefs trigger Chanmama (Douyin) + Feigua (Xiaohongshu); EN briefs trigger CreatorIQ (global)
- BGE-M3 natively handles cross-lingual embeddings — Chinese and English documents in the same Pinecone namespace are retrievable by queries in either language
- Semantic chunking splits on token count + punctuation boundaries, independent of language-specific tokenizers

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
| Tool-use structured output + typed LangGraph state | Agents produce Pydantic-validated output via `with_structured_output()` (tool_use); pipeline nodes write specific typed fields to state; downstream agents receive only the fields they need — no `json.dumps` blob passing or keyword-matching fallbacks |
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
│   │   ├── agents/               # brief_analyzer.py, research.py, strategy.py, resource.py, deck.py,
│   │   │                         # schemas.py (Pydantic output models), social_data.py, visual_analysis.py
│   │   ├── graph/                # pipeline.py (LangGraph nodes), executor.py (run/rerun),
│   │   │                         # state.py (PipelineState)
│   │   ├── rag/                  # indexer.py, retriever.py, cache.py, resource_import.py,
│   │   │                         # visual_renderer.py, visual_style.py, visual_process.py,
│   │   │                         # feedback_embedder.py
│   │   ├── language/             # router.py (language detection), prompts.py (CN/EN templates)
│   │   ├── stability/            # budget.py (RequestBudget), fallback.py (FallbackChain)
│   │   ├── models/               # resource.py, feedback.py, pipeline.py
│   │   └── database/             # connection.py, repositories (mongo collections)
│   ├── tests/                    # 105 unit tests + integration suite + load tests
│   └── Dockerfile                # Python 3.11 + LibreOffice headless + poppler-utils
├── frontend/
│   ├── app/                      # Next.js App Router pages
│   │   ├── pipeline/             # Pipeline execution + HITL confirmation UIs
│   │   ├── proposals/[id]/       # Proposal detail + FeedbackPanel + VersionPanel
│   │   ├── clients/              # Client management
│   │   ├── files/                # File library (upload, visual ref thumbnails)
│   │   ├── resources/            # Resource library (list, filter, Excel import)
│   │   ├── research/             # Research data display + refresh
│   │   └── analytics/            # Analytics dashboard (KPIs, stage perf, feedback stats)
│   ├── components/
│   │   ├── gallery/              # GalleryView, SlideThumbnail, SlidePreview, NarrativePanel
│   │   ├── hitl/                 # HITL confirmation components (Nodes 1-4)
│   │   ├── feedback/             # FeedbackPanel (Node 5)
│   │   ├── versions/             # VersionPanel (history, diff, rollback)
│   │   ├── pipeline/             # Pipeline execution status view
│   │   └── layout/               # Nav, shell
│   ├── hooks/                    # useWebSocket, usePipeline
│   └── lib/                      # api.ts (HTTP client), ws.ts (WebSocket)
├── infrastructure/
│   ├── docker/
│   │   └── docker-compose.yml    # 8 services with healthchecks
│   └── terraform/                # AWS deployment (ECS Fargate + ALB + ElastiCache + CloudWatch)
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

**Phase 3 (Production Hardening)** — Mostly complete. Version management, analytics dashboard, Terraform deployment, health checks, integration/load tests done. Remaining: Pinecone/MongoDB backup strategy, PPT template expansion, PDF export.

See [ROADMAP.md](./ROADMAP.md) for detailed progress.

---

## Documentation

- [PRD](./PRD.md) — Product requirements, user journey, feature specs
- [Architecture](./Architecture.md) — Technical design, data models, API specs
- [Roadmap](./ROADMAP.md) — Phased development plan
- [Dev Notes](./docs/dev-notes/) — Development issues and solutions

## License

Proprietary. All rights reserved.
