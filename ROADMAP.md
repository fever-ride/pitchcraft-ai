# Roadmap: Pitchcraft

## Phase 1: Core Pipeline (MVP)

End-to-end flow from brief input to PPT download with human oversight at every critical decision.

### 1.1 Infrastructure

- [ ] Docker Compose: FastAPI + Celery + Redis + MongoDB + Next.js + Nginx + BGE-M3
- [ ] MongoDB schema: organizations, users, clients, projects, proposals, files, resources, feedback, stage_metrics
- [ ] Auth: JWT login/refresh, role-based permission middleware (account / lead_account / admin)
- [ ] WebSocket: pipeline status streaming + HITL event push

### 1.2 File Management and RAG

- [ ] File upload API (PDF, PPTX, DOCX)
- [ ] File categorization: Brand Library (brand_spec, brand_history) vs Project Library (project_brief, competitor_copy)
- [ ] BGE-M3 embedding service (self-hosted)
- [ ] Semantic chunking pipeline: token-based, paragraph/sentence boundary splitting
- [ ] Pinecone namespace isolation: brand_spec_{client_id}, brand_history_{client_id}, project_{project_id}
- [ ] Soft-delete for files (running pipelines unaffected)

### 1.3 Brief Analyzer

- [ ] Natural language brief parsing
- [ ] Structured field extraction (client, theme, audience, channels, budget, timeline, objective)
- [ ] Missing field detection + clarification question generation
- [ ] Node 1: HITL confirmation via WebSocket

### 1.4 Research Agent (Basic)

- [ ] Web search via Tavily (competitor news, brand positioning, public reports)
- [ ] Internal history search via Pinecone (project namespace)
- [ ] Deterministic fallback: Tavily → DuckDuckGo → internal only
- [ ] Result timestamping (research_fetched_at in PipelineState)
- [ ] Semantic response cache (Redis, 30-day TTL, keyed by client_id:competitor:date_bucket)

### 1.5 Strategy Agent (Two-Phase)

- [ ] Phase 1 (parallel with Research): audience insights + brand direction from Brief + Brand Library
- [ ] Phase 2 (after Research): Big Idea, communication logic, channel mix, budget allocation, KPIs
- [ ] LangGraph fan-out/fan-in wiring
- [ ] Brand consistency check: strategy output vs brand_spec namespace
- [ ] Node 2: HITL confirmation with research timestamp + refresh button
- [ ] Rerun options: strategy only vs research + strategy

### 1.6 Resource Agent (KOL Only)

- [ ] Unified resource schema (type, name, tags, pricing, collaboration_history, metadata)
- [ ] KOL/KOC database with manual entry + Excel bulk import
- [ ] Pinecone resource_kol namespace for vector matching
- [ ] Trigger logic: activates only when strategy includes social channels
- [ ] Clean skip when no external resources needed

### 1.7 Deck System

- [ ] Deck Orchestrator: three-tier structure priority (global / client / project)
- [ ] Node 3: HITL structure confirmation (add/remove/reorder slides)
- [ ] Slide Content Agent: per-page content generation with brand tone enforcement via RAG
- [ ] Streaming: push each completed slide to frontend immediately (slide_generated WebSocket event)
- [ ] Narrative Agent: non-blocking coherence check, outputs suggestion list with page references
- [ ] Node 4: Gallery Review UI (thumbnail nav, preview, narrative panel, batch mark + regenerate)
- [ ] PPT Builder: python-pptx template assembly, web preview + .pptx download
- [ ] Fixed templates: one per project type (social media, PR, integrated, brand refresh)

### 1.8 Stability and Observability

- [ ] Request Budget: max 30 LLM calls, 10 search calls, 300s timeout per pipeline
- [ ] Fallback chains for each external dependency
- [ ] Per-stage metrics collection (stage_metrics MongoDB collection)
- [ ] Language Router: detect brief language, select Chinese/English prompt templates

### 1.9 Frontend (Core)

- [ ] Login + organization context
- [ ] Client management (shared Brand Library)
- [ ] Project creation + file upload
- [ ] Pipeline execution view with real-time WebSocket updates
- [ ] HITL confirmation UIs (Nodes 1-4)
- [ ] Gallery Review component (GalleryView, SlideThumbnail, SlidePreview, NarrativePanel)
- [ ] PPT preview + download page

---

## Phase 2: Research and Resource Enhancement

Deeper research, expanded resource types, client feedback loop.

### 2.1 Research Agent Enhancement

- [ ] Multimodal competitor analysis (uploaded screenshots → visual style extraction)
- [ ] Third-party social data APIs (Chanmama, Feigua) for KOL performance metrics
- [ ] Richer competitor reports: social performance, content style analysis

### 2.2 Resource Agent Expansion

- [ ] Media resource database (outlets, journalists, publish types, pricing)
- [ ] Vendor database (event companies, photographers, venues)
- [ ] Ad placement database (OOH, elevator, magazine, cinema)
- [ ] Pinecone namespaces: resource_media, resource_vendor, resource_placement
- [ ] Trigger logic expansion: PR → media, offline → vendor, ads → placement

### 2.3 Client Feedback Loop (Node 5)

- [ ] Feedback entry UI: free text + approved/rejected direction tagging
- [ ] Feedback persistence to Brand Library (influences future projects)
- [ ] Targeted rerun: system suggests rerun node based on feedback type, user confirms
- [ ] Rerun matrix: strategy / slide / structure / resource level

### 2.4 Visual Reference Processing

- [ ] Multimodal file handling for moodboards and competitor screenshots
- [ ] Visual style extraction (color palette, design language)
- [ ] Phase 2 processing pipeline integration

### 2.5 Frontend (Enhanced)

- [ ] Node 5: feedback entry + rerun trigger UI
- [ ] Resource library management interface
- [ ] Research data display with refresh controls

---

## Phase 3: Production Hardening

Version control, analytics, deployment infrastructure.

### 3.1 Version Management

- [ ] Auto-save version on each generation or modification
- [ ] Version diff view (what changed between versions)
- [ ] One-click rollback to any previous version
- [ ] Version notes

### 3.2 Analytics Dashboard

- [ ] Agent trigger rate and interception rate
- [ ] Brief Analyzer clarification frequency
- [ ] Narrative Agent suggestion acceptance rate
- [ ] Average pipeline execution time
- [ ] Request Budget usage distribution
- [ ] Cache hit rate

### 3.3 Infrastructure and DevOps

- [ ] CI/CD: GitHub Actions (pytest + lint + frontend build → Docker image push)
- [ ] Terraform deployment scripts
- [ ] Health checks and alerting
- [ ] Log aggregation
- [ ] Pinecone index backup strategy
- [ ] MongoDB backup and recovery

### 3.4 Quality of Life

- [ ] More PPT template variants per project type
- [ ] Client VI color/font customization in PPT Builder
- [ ] Batch operations (run pipeline for multiple projects)
- [ ] PDF export as alternative to .pptx

---

## Success Metrics

| Metric | Phase 1 Target |
|--------|---------------|
| Brief to PPT delivery time | < 30 minutes (vs 3-5 days manual) |
| Pipeline completion rate | > 80% without errors |
| Node 2 strategy acceptance on first try | > 60% |
| Narrative suggestions accepted | > 40% |
| Average LLM calls per pipeline | < 25 (within budget) |

---

## Open Questions

- [ ] Visual reference file processing depth (Phase 2)
- [ ] China social media data acquisition compliance
- [ ] Resource database cold-start strategy
- [ ] Resource Agent trigger boundary: Strategy output sufficient, or user selects at Node 2?
- [ ] Narrative Agent prompt design (specific, actionable, page-referenced)
- [ ] Client feedback rerun: auto-detect node vs user manual selection
- [ ] Initial PPT template count and project type coverage
