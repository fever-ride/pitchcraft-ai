# Architecture: Pitchcraft

**Version**: v0.2
**Status**: Draft
**Last updated**: 2026-05
**Related**: PRD v0.4

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                            │
│                  Next.js Frontend (Port 3000)                   │
│           React + TypeScript + Redux + WebSocket                │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS / WSS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       API GATEWAY LAYER                         │
│                      Nginx Reverse Proxy                        │
│                  HTTP → /api   WS → /ws                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                           │
│                    FastAPI Backend (Port 8000)                  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              LangGraph Multi-Agent Pipeline               │  │
│  │                                                           │  │
│  │  BriefAnalyzer → [Research ‖ StrategyP1] → StrategyP2 →   │  │
│  │  Resource → DeckOrch → SlideContent → Narrative → PPTBld  │  │
│  │                                                           │  │
│  │  ┌─────────────────┐    ┌──────────────────────────────┐ │  │
│  │  │  Request Budget  │    │   Deterministic Fallback     │ │  │
│  │  │  (per-pipeline   │    │   Chain (per external dep)   │ │  │
│  │  │   cost cap)      │    │                              │ │  │
│  │  └─────────────────┘    └──────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────┐   ┌─────────────────────────────┐    │
│  │     RAG Pipeline     │   │      Memory & Cache         │    │
│  │  - Brand Library     │   │  - Project State            │    │
│  │    (specs / history) │   │  - Semantic Response Cache  │    │
│  │  - Project Library   │   │  - Client Feedback Store    │    │
│  │    (briefs / comps)  │   │                             │    │
│  │  - Resource Index    │   │                             │    │
│  │    (KOL/media/vendor)│   │                             │    │
│  │  - BGE-M3 Embedding  │   │                             │    │
│  └──────────────────────┘   └─────────────────────────────┘    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Language Router                              │   │
│  │  - Language detection (langdetect)                       │   │
│  │  - Prompt templates: Chinese and English                 │   │
│  │  - Output language follows input, supports mixed         │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────┬──────────────────────────────┬───────────────────────┘
           │                              │
           ▼                              ▼
┌──────────────────┐            ┌──────────────────────┐
│   TASK QUEUE     │            │    EXTERNAL TOOLS    │
│  Celery + Redis  │            │  - Tavily Search     │
│  - PPT generation │            │  - Anthropic API     │
│  - File indexing  │            │  - python-pptx       │
│  - Research tasks │            │                      │
└──────────────────┘            └──────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                             │
│                                                                 │
│  ┌────────────────────────┐    ┌───────────────────────────┐   │
│  │      MongoDB Atlas     │    │        Pinecone DB        │   │
│  │                        │    │                           │   │
│  │  - organizations       │    │  brand_spec_{client_id}   │   │
│  │  - users               │    │  brand_history_{client_id}│   │
│  │  - clients             │    │  project_{project_id}     │   │
│  │  - projects            │    │  resource_kol             │   │
│  │  - proposals           │    │  resource_media           │   │
│  │  - files               │    │  resource_vendor          │   │
│  │    (brand & project)   │    │  resource_placement       │   │
│  │  - resources           │    │                           │   │
│  │    (kol/media/vendor/  │    │  (namespace isolation     │   │
│  │     placement)         │    │   prevents cross-index    │   │
│  │  - feedback            │    │   contamination)          │   │
│  │  - stage_metrics       │    │                           │   │
│  └────────────────────────┘    └───────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent System Design

### 2.1 LangGraph State Machine

The entire pipeline is managed by LangGraph. It supports conditional branching, human-in-the-loop pauses, and targeted reruns.

```python
class PipelineState(TypedDict, total=False):
    # Identity
    client_id: str
    project_id: str
    proposal_id: str

    # Brief
    raw_brief: str
    structured_brief: dict          # BriefAnalyzer output
    brief_confirmed: bool           # Node 1 user confirmation

    # Research + Strategy
    research_result: dict           # Research Agent output
    research_fetched_at: float      # Research completion timestamp
    strategy_insight: dict          # Strategy Phase 1 output (audience, brand direction)
    strategy_result: dict           # Strategy Phase 2 output (full strategy)
    brand_check_passed: bool        # Brand consistency check result

    # Strategy confirmation
    strategy_confirmed: bool        # Node 2 user confirmation
    strategy_feedback: str          # User revision notes

    # Resources
    resource_result: dict           # Resource Agent output
    resource_types_needed: list     # ["kol", "media", "vendor"]

    # Deck
    deck_structure: list            # Slide list
    structure_confirmed: bool       # Node 3 user confirmation
    slides: list                    # Per-slide content
    slides_confirmed: bool          # Node 4 user confirmation
    narrative_suggestions: list     # Narrative suggestions (non-blocking)

    # Output
    pptx_path: str

    # Control
    rerun_from: str                 # Targeted rerun start node
    rerun_refresh_research: bool    # Whether to also refresh Research on Strategy rerun
    request_budget: RequestBudget   # Cost control
    stage_metrics: dict             # Per-stage value tracking
```

### 2.2 Parallelism and Synchronization

Research Agent and Strategy Phase 1 launch simultaneously (fan-out). Strategy Phase 2 waits for both to complete (fan-in). In LangGraph, when multiple edges point to the same node, it automatically waits for all upstream nodes:

```python
# Fan-out: both start after brief confirmation
graph.add_edge("brief_confirmed", "research_agent")
graph.add_edge("brief_confirmed", "strategy_phase1")

# Fan-in: strategy_phase2 waits for both
graph.add_edge("research_agent", "strategy_phase2")
graph.add_edge("strategy_phase1", "strategy_phase2")
```

### 2.3 Agent Topology

```
                    ┌─────────────────┐
                    │  Brief Analyzer  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  [Node 1] User   │  ← HITL
                    │  Confirm brief   │    WebSocket push, await frontend response
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │        Parallel              │
              ▼                             ▼
    ┌──────────────────┐         ┌──────────────────┐
    │  Research Agent  │         │ Strategy Phase 1 │
    │  - Web search    │         │  - Audience      │
    │  - Competitor    │         │    insights      │
    │    analysis      │         │  - Brand         │
    │  - Visual        │         │    direction     │
    │    analysis      │         │  (no competitor  │
    │                  │         │   dependency)    │
    └────────┬─────────┘         └────────┬─────────┘
              │                            │
              └──────────────┬─────────────┘
                             │ Fan-in sync point
                    ┌────────▼────────┐
                    │ Strategy Phase 2│  ← Integrates Research results
                    │  - Big Idea     │    Generates full strategy
                    │  - Comm logic   │
                    │  - Channel mix  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Brand check    │  ← RAG retrieves Brand Library
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  [Node 2] User   │  ← Most critical checkpoint
                    │  Confirm strategy│    Shows Research timestamp + [Refresh]
                    │                  │    Rerun: strategy only / research+strategy
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Resource Agent │  ← Optional, triggers by channel type
                    │  (pluggable)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Deck Orchestrator│  ← Three-tier structure priority
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  [Node 3] User   │
                    │  Confirm structure│
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Slide Content   │  ← Per-slide generation with copy
                    │    Agent        │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │     After completion         │
              ▼                             ▼
    ┌──────────────────┐         ┌──────────────────┐
    │  [Node 4] User    │         │ Narrative Agent  │
    │  Gallery ready    │         │ Background check │
    └────────┬─────────┘         └────────┬─────────┘
              │                            │
              │    Suggestions pushed       │
              │◄───────────────────────────┘
              │
    ┌────────▼────────┐
    │  [Node 4] User   │  ← Left: slide content
    │  Gallery Review  │    Right: Narrative suggestions
    └────────┬────────┘
              │
    ┌────────▼────────┐
    │   PPT Builder   │  ← Deterministic, no business logic
    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  [Node 5] Client │
                    │  Feedback entry  │  ← Persists to Brand Library
                    │                  │    Triggers targeted rerun
                    └─────────────────┘
```

---

## 3. RAG System Design

### 3.1 Pinecone Namespace Index Structure

Different file types and resources use isolated namespaces to prevent cross-index contamination and allow per-type tuning of retrieval weights.

```
Pinecone Index: pitchcraft
│
│  ── Brand Library (long-term) ───────────────────────────────
├── namespace: brand_spec_{client_id}
│       Brand spec files
│       VI guide, brand book, Tone of Voice, design guidelines
│       Retrieval purpose: brand consistency check (Strategy output comparison)
│       Chunk size: 256 tokens (short chunks for higher precision on normative text)
│       Lifecycle: persistent, reused across projects
│
├── namespace: brand_history_{client_id}
│       Historical proposals + brand content
│       Past campaign decks, strategy docs, historical copy, social content
│       Retrieval purpose: style reference (Slide Content Agent copy generation)
│       Chunk size: proposals 512 tokens, copy 128 tokens (split on sentence boundaries)
│       Lifecycle: persistent, accumulates over time
│
│  ── Project Library (temporary) ─────────────────────────────
├── namespace: project_{project_id}
│       Project-level files, archived after project ends
│       Requirements docs, client brief, meeting notes, competitor materials
│       Retrieval purpose: brief context, Strategy Phase 1 project reference
│       Chunk size: 384 tokens
│       Lifecycle: project duration, marked archived on completion
│
│  ── Resource Index ──────────────────────────────────────────
├── namespace: resource_kol
│       KOL/KOC profile text (platform, content direction, audience, style)
│       Retrieval purpose: audience + style vector matching
│
├── namespace: resource_media
│       Media outlet descriptions (positioning, coverage, audience traits)
│       Retrieval purpose: industry + audience vector matching
│
├── namespace: resource_vendor
│       Vendor descriptions (service types, specialties, past work)
│       Retrieval purpose: event type + region vector matching
│
└── namespace: resource_placement
        Placement descriptions (type, cities, audience scenarios)
        Retrieval purpose: region + audience vector matching
```

### 3.2 Namespace Retrieval Reference

| Scenario | Agent | Namespace | Retrieval logic |
|----------|-------|-----------|----------------|
| Brand consistency check | After Strategy Agent | brand_spec_{client_id} | Strategy keywords vs brand spec semantic similarity |
| Copy style reference | Slide Content Agent | brand_history_{client_id} | Tone descriptors retrieve historical copy styles |
| Historical campaign reference | Strategy P2, Media Planning, Resource, Deck, Brief Analyzer | campaign_knowledge_{org_id} | Proposition vectors + self-verification quality gate; per-agent retrieval profiles control top_k and module whitelist |
| KOL matching | Resource Agent | resource_kol | Audience profile + content direction vectors |
| Media matching | Resource Agent | resource_media | Industry + audience trait vectors |
| Vendor matching | Resource Agent | resource_vendor | Event type + region vectors |
| Placement matching | Resource Agent | resource_placement | Audience scenario + city vectors |

### 3.3 File Processing Pipeline

```
User uploads file (PDF / PPTX / DOCX / image)
        ↓
Celery async task receives
        ↓
Determine file destination
├── Has project_id → Project Library
└── No project_id → Brand Library
        ↓
Identify file type (determines namespace and chunk strategy)
├── brand_spec    → brand_spec_{client_id}
├── brand_history → brand_history_{client_id}
├── project_doc   → project_{project_id}
├── competitor    → project_{project_id}
└── visual_ref    → store in MongoDB, Phase 2 multimodal processing
        ↓
Format parsing
├── PDF  → pypdf (text extraction)
├── PPTX → python-pptx (extract text + page structure)
├── DOCX → python-docx
└── visual_ref → Phase 2 multimodal pipeline (see 3.4)
        ↓
Semantic chunking
├── Unit: tokens (BGE-M3 tokenizer)
├── Strategy: semantic boundaries first (paragraph → sentence), no fixed-length hard cuts
├── Overlap: sentence-level overlap, never splits mid-boundary
├── Mixed Chinese/English: no special handling, BGE-M3 natively supports mixed input
└── Max tokens per type: see 3.1
        ↓
Embedding (BGE-M3, self-hosted, max input 8192 tokens)
        ↓
Write to corresponding Pinecone namespace
        ↓
Write metadata to MongoDB files collection
(filename, file_category, file_type, namespace, processing_status)
```

### 3.4 Visual Reference Processing Pipeline (Phase 2)

Design decks and moodboards contain minimal extractable text. A multimodal pipeline converts visual slides into structured style descriptions for embedding.

```
User uploads visual_ref file (PPTX / PDF)
        ↓
Celery task: process_visual_file_task
        ↓
Render to images
├── PPTX → LibreOffice headless → PNG per slide
└── PDF  → pdf2image (poppler) → PNG per page
        ↓
Filter: skip slides with >80% text area (already in text pipeline)
        ↓
Claude Vision analysis (batched, 5 slides per request)
        ↓
Per-slide structured output:
{
  "slide_index": 3,
  "color_palette": {
    "primary": "#1A2B5E",
    "secondary": "#F5A623",
    "accent": "#FFFFFF",
    "background": "#F8F8F8"
  },
  "layout_pattern": "left-right split, image left, text right",
  "typography": {
    "heading": "sans-serif, bold, high contrast",
    "body": "sans-serif, regular, 14-16pt equivalent"
  },
  "image_text_ratio": 0.65,
  "visual_density": "moderate",
  "design_keywords": ["corporate", "clean", "data-driven"],
  "notable_elements": ["line charts", "icon set", "photography: office/team"]
}
        ↓
Aggregate across all slides → Visual Identity Summary:
{
  "dominant_colors": ["#1A2B5E", "#F5A623"],
  "primary_layout": "left-right split",
  "typography_family": "sans-serif",
  "overall_density": "moderate",
  "design_language": "corporate clean with data visualization focus",
  "photography_style": "professional team/office shots, natural lighting"
}
        ↓
Embed: per-slide descriptions + summary → brand_spec_{client_id} namespace
Store: PNG thumbnails → object storage (for UI preview)
Update: MongoDB file record (chunk_count, processing_status, thumbnail_urls)
```

**Claude Vision prompt structure:**

```
Analyze this presentation slide as a design reference. Do not describe the
content/message. Focus only on visual design attributes.

Output a JSON object with these fields:
- color_palette: {primary, secondary, accent, background} as hex
- layout_pattern: describe the spatial arrangement in one phrase
- typography: {heading, body} describe style, not content
- image_text_ratio: float 0-1 (1 = all image)
- visual_density: "minimal" | "moderate" | "dense"
- design_keywords: 3-5 style descriptors
- notable_elements: list of visual elements present
```

**Downstream usage:**

| Consumer | What it retrieves | How it uses it |
|----------|------------------|----------------|
| PPT Builder | Visual Identity Summary | Select matching template, set color scheme and fonts |
| Slide Content Agent | Per-slide layout patterns | Adjust copy length to match visual density |
| Brand Check | Design keywords | Flag if strategy tone contradicts visual identity |

**Cost estimation:**

Assuming 15 slides per file, 5 slides per Vision request = 3 API calls per file.
At ~$0.02/image (Claude Vision pricing), processing one deck costs ~$0.30.
Batch mode and skip-text-heavy filter reduce this by ~30% in practice.

---

## 4. Stability Design

### 4.1 Request Budget

Each pipeline execution has resource caps to prevent agent loops or runaway external calls:

```python
@dataclass
class RequestBudget:
    max_llm_calls: int = 30        # Max LLM calls per pipeline
    max_search_calls: int = 10     # Max searches for Research Agent
    max_retry_per_agent: int = 2   # Max retries per individual agent
    max_total_seconds: int = 300   # 5 minute pipeline timeout
    current_llm_calls: int = 0
    current_search_calls: int = 0
    start_time: float = field(default_factory=time.time)

    def check(self) -> None:
        if self.current_llm_calls >= self.max_llm_calls:
            raise BudgetExceeded("LLM call limit reached")
        if time.time() - self.start_time > self.max_total_seconds:
            raise BudgetExceeded("Pipeline timeout")
```

### 4.2 Deterministic Fallback Chains

Every external dependency has an ordered degradation path. No single failure blocks the entire flow:

```
Tavily search fails
    → Fall back to DuckDuckGo
    → Return empty web results (Research proceeds with brief context only)

Pinecone fails
    → Fall back to MongoDB full-text search
    → Mark RAG result as "degraded mode"

LLM timeout
    → Retry once
    → Switch to backup model
    → Return template content + warning

python-pptx generation fails
    → Fall back to Markdown format proposal
    → Notify user PPT generation failed, provide text version
```

### 4.3 Semantic Response Cache

Caches Research Agent web search results to avoid redundant searches:

```
Cache key: {client_id}:{search_query_prefix}:{date_bucket}
date_bucket: 30-day buckets (reuse research data within 30 days)

Hit conditions:
- Same client_id
- Same search query prefix (first 50 chars)
- Within same 30-day bucket

On hit: return cached Research result
        Label result as "source: cache ({date})"
        Let user decide whether to force refresh

Known limitation: query prefix truncation can cause cache collisions
across different briefs for the same client (tracked in ROADMAP 3.8)
```

Storage: Redis, TTL = 30 days

---

## 5. Observability

### 5.1 Per-Stage Metrics

Tracks actual value of each agent node. Stored in MongoDB:

```python
stage_metrics = {
    "project_id": "...",
    "brief_analyzer": {
        "clarification_triggered": True,
        "missing_fields": ["kpi", "budget"]
    },
    "brand_consistency_check": {
        "triggered_revision": False,
        "issues_found": []
    },
    "narrative_agent": {
        "suggestions_count": 2,
        "suggestions_accepted": 1,
        "suggestions_ignored": 1,
        "suggestions_detail": ["insight-strategy mismatch", "budget-channel priority conflict"]
    },
    "resource_agent": {
        "triggered": True,
        "resource_types": ["kol", "media"],
        "matched_count": 8
    },
    "request_budget": {
        "llm_calls_used": 18,
        "search_calls_used": 5,
        "total_seconds": 142
    }
}
```

### 5.2 Analytics Dashboard (Frontend)

Based on stage_metrics data:

- Agent trigger rate and interception rate
- Brief Analyzer clarification frequency (which fields clients most often omit)
- Narrative Agent suggestion type distribution (which coherence issues are most common)
- Average pipeline execution time
- Request Budget usage distribution (cost analysis)
- Cache hit rate

---

## 6. Tech Stack

### 6.1 Backend

| Component | Technology | Version | Notes |
|-----------|-----------|---------|-------|
| API framework | FastAPI | 0.115 | Async REST + WebSocket |
| Auth | Google OAuth + Microsoft OAuth + JWT | - | NextAuth on frontend, JWT tokens on backend |
| Agent orchestration | LangGraph | 0.2 | State machine + HITL support |
| LLM | Claude Sonnet | - | Primary model |
| Embedding | BGE-M3 (self-hosted) | - | Multilingual (Chinese + English), strong marketing terminology support |
| Web search | Tavily | - | Research Agent search tool |
| Task queue | Celery + Redis | 5.3 / 7 | Async heavy tasks |
| PPT generation | python-pptx | - | Deck output |
| PDF parsing | PyPDF2 | - | File processing |

### 6.2 Data Layer

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Primary database | MongoDB Atlas | Clients, projects, proposals, feedback, metrics |
| Vector database | Pinecone | RAG retrieval (namespace isolated); namespaces: brand_spec_{client_id}, brand_history_{client_id}, resource_{type}, campaign_knowledge_{org_id} |
| Cache | Redis | Celery broker + semantic cache |

### 6.3 Frontend

| Component | Technology | Notes |
|-----------|-----------|-------|
| Framework | Next.js 14 | App Router + SSR |
| Language | TypeScript | Type safety |
| State management | Redux Toolkit | Global state + RTK Query |
| Real-time | WebSocket | Agent streaming + HITL node push |
| Styling | Tailwind CSS | Utility-first |

### 6.4 Infrastructure

| Component | Technology | Notes |
|-----------|-----------|-------|
| Containerization | Docker + Docker Compose | Local dev and deployment |
| Reverse proxy | Nginx | Routing + SSL |
| CI/CD | GitHub Actions | Auto test + Docker build |
| Code quality | Black + isort + flake8 | Formatting and lint |
| Testing | pytest | Unit tests |

---

## 7. MongoDB Data Model

```
collections:
│
├── organizations                   # Agency company (top-level tenant)
│   ├── _id
│   ├── name
│   └── created_at
│
├── users                           # Account users
│   ├── _id
│   ├── organization_id             # Which agency
│   ├── name
│   ├── email
│   ├── role                        # account / lead_account / admin
│   └── created_at
│
├── clients                         # Clients (shared across org)
│   ├── _id
│   ├── organization_id             # Which agency
│   ├── lead_account_id             # Client owner
│   ├── name
│   ├── industry
│   ├── default_deck_structure      # Client-level default slide structure
│   └── created_at
│
├── projects                        # Pitch projects
│   ├── _id
│   ├── client_id
│   ├── assigned_accounts           # [user_id] accounts assigned to this project
│   ├── name
│   ├── status                      # draft / in_progress / completed / archived
│   ├── custom_deck_structure       # Project-level structure (highest priority)
│   └── created_at
│
├── proposals                       # Proposal versions
│   ├── _id
│   ├── project_id
│   ├── created_by                  # user_id
│   ├── version                     # v1, v2, v3...
│   ├── structured_brief
│   ├── strategy_result
│   ├── deck_structure
│   ├── slides
│   ├── pptx_path
│   ├── stage_metrics
│   └── created_at
│
│  ── File Library ──────────────────────────────────────────────
│
├── files                           # All uploaded file metadata
│   ├── _id
│   ├── client_id
│   ├── project_id                  # null = Brand Library; set = Project Library
│   ├── uploaded_by                 # user_id
│   ├── filename
│   ├── file_category               # brand_library / project_library
│   ├── file_type
│   │     Under brand_library:
│   │       brand_spec              # VI, brand book, ToV
│   │       brand_history_proposal  # Historical pitch decks
│   │       brand_history_copy      # Historical copy, social content
│   │     Under project_library:
│   │       project_brief           # Client brief, meeting notes
│   │       competitor_copy         # Competitor copy, competitor materials
│   │       visual_ref              # Moodboard, competitor screenshots (Phase 2)
│   ├── pinecone_namespace          # Target namespace
│   ├── chunk_count                 # Number of chunks produced
│   ├── processing_status           # pending / processing / done / failed
│   ├── processing_error            # Failure reason
│   ├── deleted                     # Soft-delete flag (bool)
│   ├── deleted_at
│   ├── deleted_by                  # user_id
│   └── uploaded_at
│
│  ── Resource Library ──────────────────────────────────────────
│
├── resources                       # Unified resource store (all 4 types in one collection)
│   ├── _id
│   ├── type                        # kol / media / vendor / placement
│   ├── name
│   ├── tags                        # Tag array, schema varies by type
│   ├── pricing                     # { min, max, unit, currency }
│   ├── collaboration_history       # [{ client, project_type, date, performance }]
│   ├── pinecone_namespace          # Maps to resource_{type} namespace
│   └── metadata                    # Type-specific fields (see below)
│
│   KOL metadata:
│   { platform, followers, content_direction, audience_profile,
│     mcn, contact, engagement_rate }
│
│   Media metadata:
│   { media_name, media_type, coverage_domain, contact_name,
│     contact_line, publish_types }
│
│   Vendor metadata:
│   { service_types, regions, past_clients, quality_rating }
│
│   Placement metadata:
│   { placement_type, cities, audience_size, available_periods }
│
│  ── Feedback & Learning ───────────────────────────────────────
│
├── feedback                        # Client feedback
│   ├── _id
│   ├── proposal_id
│   ├── client_id
│   ├── content                     # Raw feedback text
│   ├── approved_directions         # Approved directions (persist to Brand Library)
│   ├── rejected_directions         # Rejected directions (auto-avoid in future)
│   ├── rerun_triggered             # bool
│   ├── rerun_from_node             # strategy / resource / deck_structure / slide / null
│   └── created_at
│
├── stage_metrics                   # Per-stage execution metrics (separate collection for aggregation)
│   ├── _id
│   ├── proposal_id
│   ├── project_id
│   ├── client_id
│   ├── brief_analyzer              # { clarification_triggered, missing_fields }
│   ├── brand_consistency_check     # { triggered_revision, issues_found }
│   ├── research_agent              # { sources_used, cache_hit, search_count }
│   ├── narrative_agent             # { suggestions_count, suggestions_accepted, suggestions_ignored }
│   ├── resource_agent              # { triggered, resource_types, matched_count }
│   ├── request_budget              # { llm_calls_used, search_calls_used, total_seconds }
│   └── created_at
│
│  ── Campaign Knowledge Base ────────────────────────────────────
│
├── campaign_records                # Structured extraction of past campaigns and proposals
│   ├── _id                         # Explicit string ID
│   ├── org_id                      # Org-level tenant isolation
│   ├── client_id                   # FK → clients
│   ├── project_id                  # FK → projects (optional)
│   ├── record_type                 # "campaign" | "proposal" (LLM auto-detected)
│   ├── status                      # pending_confirmation | confirmed
│   ├── confidence                  # high | partial | low (worst of participating LLM calls)
│   ├── pitch_outcome               # won | lost | unknown (proposals only; set manually at confirmation)
│   ├── meta                        # { campaign_type, campaign_subtype, industry, budget_tier,
│   │                               #   target_audience_summary, client_name, channels_used[], ... }
│   ├── strategy_decisions          # { big_idea, positioning, rejected_directions[], ... }
│   ├── communication_plan          # { channel_mix[], phasing_structure, phasing_rhythm }
│   ├── media_plan                  # { budget_total, channel_budget_split[], tier_structure[] }
│   ├── execution                   # { kol_list[], pr_activities[], event_details[], ... }
│   ├── outcome                     # { kpi_results[], lessons_learned, overall_rating }
│   ├── deck_info                   # { slide_count, deck_structure_type, key_slides[] }
│   ├── client_learnings            # { decision_style, approved_directions[], rejected_directions[] }
│   └── created_at
│
└── campaign_propositions           # Atomic insight statements extracted from confirmed records
    ├── _id
    ├── campaign_record_id          # FK → campaign_records
    ├── org_id
    ├── text                        # "[industry | subtype | budget | audience] <insight>"
    └── created_at
```

---

## 8. API Endpoints

```
Auth (Google OAuth + Microsoft OAuth + email/password fallback)
POST   /api/v1/auth/login              # Email/password
POST   /api/v1/auth/refresh
GET    /api/v1/auth/google             # Google OAuth redirect
GET    /api/v1/auth/google/callback
GET    /api/v1/auth/microsoft          # Microsoft OAuth redirect
GET    /api/v1/auth/microsoft/callback

Users
GET    /api/v1/users                         # List users in current org
POST   /api/v1/users/invite                  # Invite new Account (admin only)
PATCH  /api/v1/users/{id}/role               # Change role (admin only)

Clients (shared across org)
GET    /api/v1/clients
POST   /api/v1/clients
PATCH  /api/v1/clients/{id}/deck-structure   # Set client-level default (lead_account+)

Projects
GET    /api/v1/projects?client_id=...
POST   /api/v1/projects
PATCH  /api/v1/projects/{id}

Files
POST   /api/v1/files/upload                  # Upload (async processing)
GET    /api/v1/files?client_id=&project_id=
DELETE /api/v1/files/{id}

Pipeline
POST   /api/v1/pipeline/start               # Start pipeline
POST   /api/v1/pipeline/{id}/confirm        # HITL node user confirmation
POST   /api/v1/pipeline/{id}/rerun          # Targeted rerun (body includes refresh_research option)
GET    /api/v1/pipeline/{id}/status         # Query execution status

Proposals
GET    /api/v1/proposals?project_id=...
GET    /api/v1/proposals/{id}
GET    /api/v1/proposals/{id}/download      # Download .pptx
POST   /api/v1/proposals/{id}/feedback      # Record client feedback

Resources
GET    /api/v1/resources?type=&tags=
POST   /api/v1/resources
POST   /api/v1/resources/import             # Excel bulk import

Analytics
GET    /api/v1/analytics/pipeline-metrics   # Stage metrics summary
GET    /api/v1/analytics/cache-stats        # Cache hit rate

System
GET    /health
WS     /ws/pipeline/{pipeline_id}           # Real-time agent execution status
```

---

## 9. WebSocket Events

The frontend receives pipeline execution status in real time via WebSocket for streaming display and HITL interaction:

```
Server → Client:
{
  "event": "agent_started",
  "agent": "research_agent",
  "message": "Searching competitor information..."
}

{
  "event": "agent_completed",
  "agent": "strategy_agent",
  "output": { ...strategy_result }
}

{
  "event": "hitl_required",
  "node": "node_2_strategy",
  "data": { ...strategy_result },
  "message": "Please confirm strategy direction"
}

{
  "event": "slide_generated",
  "slide_index": 3,
  "total_slides": 15,
  "content": { ...slide_content }
}

{
  "event": "narrative_suggestions",
  "suggestions": [
    { "page": 3, "issue": "Insight on page 3 conflicts with strategy on page 5" },
    { "page": 7, "issue": "Budget allocation conflicts with channel priorities" }
  ]
}

{
  "event": "pipeline_completed",
  "pptx_url": "/api/v1/proposals/xxx/download"
}

{
  "event": "budget_warning",
  "message": "LLM calls at 80% of limit"
}

{
  "event": "fallback_triggered",
  "agent": "research_agent",
  "reason": "Tavily unavailable, switched to DuckDuckGo"
}

Client → Server:
{
  "event": "hitl_response",
  "node": "node_2_strategy",
  "action": "confirm",
  "feedback": "Big Idea direction is off, want more tech-focused",
  "refresh_research": false
}

{
  "event": "research_refresh",
  "node": "node_2_strategy"
}
```

---

## 10. Docker Compose Services

```yaml
services:
  frontend:        # Next.js,  Port 3000
  backend:         # FastAPI,  Port 8000
  worker:          # Celery Worker (file processing + PPT generation)
  embedding:       # BGE-M3 embedding service (Port 8001)
  redis:           # Port 6379 (Celery broker + semantic cache)
  mongodb:         # Port 27017
  nginx:           # Port 80/443 (reverse proxy)

networks:
  pitchcraft_network

volumes:
  mongodb_data
  redis_data
  pptx_output      # Generated PPT files
  uploaded_files   # User-uploaded raw files
```

---

## 11. CI/CD Pipeline

```
git push
    ↓
GitHub Actions triggers
    │
    ├── Parallel
    │   ├── pytest (backend unit tests)
    │   ├── lint (Black + flake8)
    │   └── frontend build check
    │
    └── All pass
            ↓
        Build Docker images
            ↓
        Push to Docker Hub
            ↓
        Ready to deploy
```

---

## 12. Project Directory Structure

```
pitchcraft/
├── backend/
│   ├── api/
│   │   ├── main.py
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py
│   │       │   ├── users.py
│   │       │   ├── clients.py
│   │       │   ├── projects.py
│   │       │   ├── files.py
│   │       │   ├── pipeline.py
│   │       │   ├── proposals.py
│   │       │   ├── resources.py
│   │       │   └── analytics.py
│   │       ├── permissions.py       # Role-based permission checks
│   │       └── websocket.py
│   ├── core/
│   │   ├── agents/
│   │   │   ├── brief_analyzer.py
│   │   │   ├── research_agent.py
│   │   │   ├── strategy_agent.py
│   │   │   ├── resource_agent.py
│   │   │   ├── deck_orchestrator.py
│   │   │   ├── slide_content_agent.py
│   │   │   ├── narrative_agent.py
│   │   │   └── ppt_builder.py
│   │   ├── graph/
│   │   │   ├── pipeline.py          # LangGraph main flow
│   │   │   ├── state.py             # PipelineState definition
│   │   │   └── nodes.py             # Node functions
│   │   ├── rag/
│   │   │   ├── indexer.py           # File vectorization
│   │   │   ├── retriever.py         # Retrieval logic
│   │   │   └── cache.py             # Semantic cache
│   │   ├── language/
│   │   │   ├── detector.py          # Language detection
│   │   │   └── prompts.py           # Chinese/English prompt templates
│   │   ├── stability/
│   │   │   ├── budget.py            # Request Budget
│   │   │   └── fallback.py          # Fallback chains
│   │   ├── database/
│   │   │   └── repositories/        # MongoDB operations
│   │   ├── models/                  # Pydantic models
│   │   ├── tasks.py                 # Celery tasks
│   │   └── config.py
│   ├── tests/
│   │   └── unit/
│   └── requirements.txt
├── frontend/
│   ├── app/                         # Next.js App Router
│   ├── components/
│   │   ├── pipeline/                # Pipeline execution view
│   │   ├── hitl/                    # HITL confirmation components
│   │   ├── gallery/                 # Node 4 Gallery Review
│   │   │   ├── GalleryView.tsx      # Main layout (thumbnails + preview + progress)
│   │   │   ├── SlideThumbnail.tsx   # Thumbnail with status indicator
│   │   │   ├── SlidePreview.tsx     # Current slide preview
│   │   │   └── NarrativePanel.tsx   # Narrative suggestions panel
│   │   ├── deck-preview/            # PPT preview
│   │   └── analytics/               # Dashboard
│   ├── store/                       # Redux
│   ├── hooks/
│   │   └── usePipelineSocket.ts     # WebSocket hook
│   └── types/
├── infrastructure/
│   └── docker/
│       └── docker-compose.yml
├── .github/
│   └── workflows/
│       └── ci.yml
└── README.md
```
