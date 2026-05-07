# Roadmap: Pitchcraft

## Phase 1: Core Pipeline (MVP)

End-to-end flow from brief input to PPT download with human oversight at every critical decision.

### 1.1 Infrastructure

- [x] Docker Compose: FastAPI + Celery + Redis + MongoDB + Next.js + Nginx + BGE-M3
- [x] MongoDB schema: organizations, users, clients, projects, proposals, files, resources, feedback, stage_metrics
- [x] Auth: Google OAuth + Microsoft OAuth + email/password fallback, JWT tokens, role-based permissions (account / lead_account / admin)
- [x] WebSocket: pipeline status streaming + HITL event push

### 1.2 File Management and RAG

- [x] File upload API (PDF, PPTX, DOCX)
- [x] File categorization: Brand Library (brand_spec, brand_history) vs Project Library (project_brief, competitor_copy)
- [x] BGE-M3 embedding service (self-hosted)
- [x] Semantic chunking pipeline: token-based, paragraph/sentence boundary splitting
- [x] Pinecone namespace isolation: brand_spec_{client_id}, brand_history_{client_id}, project_{project_id}
- [x] Soft-delete for files (running pipelines unaffected)

### 1.3 Brief Analyzer

- [x] Natural language brief parsing
- [x] Structured field extraction (client, theme, audience, channels, budget, timeline, objective)
- [x] Missing field detection + clarification question generation
- [x] Node 1: HITL confirmation via WebSocket

### 1.4 Research Agent (Basic)

- [x] Web search via Tavily (competitor news, brand positioning, public reports)
- [x] Internal history search via Pinecone (project namespace)
- [x] Deterministic fallback: Tavily → DuckDuckGo → internal only
- [x] Result timestamping (research_fetched_at in PipelineState)
- [x] Semantic response cache (Redis, 30-day TTL, keyed by client_id:competitor:date_bucket)

### 1.5 Strategy Agent (Two-Phase)

- [x] Phase 1 (parallel with Research): audience insights + brand direction from Brief + Brand Library
- [x] Phase 2 (after Research): Big Idea, communication logic, channel mix, budget allocation, KPIs
- [x] LangGraph fan-out/fan-in wiring
- [x] Brand consistency check: strategy output vs brand_spec namespace
- [x] Node 2: HITL confirmation with research timestamp + refresh button
- [x] Rerun options: strategy only vs research + strategy

### 1.6 Resource Agent (KOL Only)

- [x] Unified resource schema (type, name, tags, pricing, collaboration_history, metadata)
- [ ] KOL/KOC database with manual entry + Excel bulk import
- [x] Pinecone resource_kol namespace for vector matching
- [x] Trigger logic: activates only when strategy includes social channels
- [x] Clean skip when no external resources needed

> **Note**: Resources endpoint exists with create/import stubs but the actual Excel parsing logic and Pinecone indexing on resource creation are not yet implemented. The endpoint structures and model schema are in place; needs the processing logic (openpyxl parse → MongoDB insert → embed → Pinecone upsert).

### 1.7 Deck System

- [x] Deck Orchestrator: three-tier structure priority (global / client / project)
- [x] Node 3: HITL structure confirmation (add/remove/reorder slides)
- [x] Slide Content Agent: per-page content generation with brand tone enforcement via RAG
- [x] Streaming: push each completed slide to frontend immediately (slide_generated WebSocket event)
- [x] Narrative Agent: non-blocking coherence check, outputs suggestion list with page references
- [x] Node 4: Gallery Review UI (thumbnail nav, preview, narrative panel, batch mark + regenerate)
- [x] PPT Builder: python-pptx template assembly, web preview + .pptx download
- [ ] Fixed templates: one per project type (social media, PR, integrated, brand refresh)

> **Note**: Deck Orchestrator currently generates structure via LLM but does not yet query the three-tier priority chain (project custom → client default → global template) from the database before prompting. The `custom_deck_structure` and `default_deck_structure` fields exist in the models but the orchestrator does not read them. Also, no actual `.pptx` template files exist yet in `backend/templates/pptx/` — the PPT Builder falls back to a blank Presentation. Need to create 4 template files with proper layouts/styles.

### 1.8 Stability and Observability

- [x] Request Budget: max 30 LLM calls, 10 search calls, 300s timeout per pipeline
- [x] Fallback chains for each external dependency
- [x] Per-stage metrics collection (stage_metrics MongoDB collection)
- [x] Language Router: detect brief language (Chinese / English), select matching prompt templates

> **Note**: Budget enforcement exists in state definition but agents do not yet call `budget.use_llm_call()` / `budget.use_search_call()` before making external requests. The executor saves metrics after completion but doesn't enforce budget during execution. Needs a middleware pattern or wrapper that each agent calls.

### 1.9 Frontend (Core)

- [x] Login + organization context
- [x] Client management (shared Brand Library)
- [x] Project creation + file upload
- [x] Pipeline execution view with real-time WebSocket updates
- [x] HITL confirmation UIs (Nodes 1-4)
- [x] Gallery Review component (GalleryView, SlideThumbnail, SlidePreview, NarrativePanel)
- [x] PPT preview + download page

> **Note**: Organization context is implicit (derived from JWT). There is no organization switching UI or org-level settings page — single-org per user assumed. Login page handles OAuth token redirect from query params but does not yet have the client-side token extraction logic (needs a small `useEffect` in `/login` to read `?token=` from URL after OAuth callback).

---

## Phase 2: Research and Resource Enhancement

Deeper research, expanded resource types, client feedback loop.

### 2.1 Research Agent Enhancement

- [ ] Multimodal competitor analysis (uploaded screenshots → visual style extraction)
- [ ] Third-party social data APIs (locale-specific: Chanmama/Feigua for China, CreatorIQ/Sprout Social for global)
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

Design decks and moodboards are primarily visual. Text extraction is near-useless for these files. This phase adds a multimodal pipeline that converts visual content into structured style descriptions, then embeds them as text for downstream RAG retrieval.

**Pipeline:**
- [ ] PPTX/PDF → per-page PNG rendering (LibreOffice headless in Docker sidecar)
- [ ] PNG → Claude Vision analysis (structured style JSON per slide)
- [ ] Style JSON → text description → BGE-M3 embedding → Pinecone `brand_spec_{client_id}`
- [ ] Batch processing: skip slides with >80% text content (already handled by text pipeline)
- [ ] Thumbnail storage: save low-res PNGs to object storage for UI preview

**Style extraction schema (Claude Vision output per slide):**
- [ ] Color palette: primary, secondary, accent, background (hex values)
- [ ] Layout pattern: e.g. "full-bleed image", "left-right split", "centered title + subtitle"
- [ ] Typography style: serif/sans-serif, weight hierarchy, size contrast
- [ ] Image-to-text ratio: percentage estimate
- [ ] Visual density: minimal / moderate / dense
- [ ] Design keywords: 3-5 descriptors (e.g. "corporate", "playful", "tech-forward")
- [ ] Notable elements: icons, charts, illustrations, photography style

**Aggregation (file-level summary):**
- [ ] After all slides processed, generate a file-level "Visual Identity Summary"
- [ ] Summarize dominant patterns across slides (most frequent layout, consistent colors)
- [ ] Store as a single high-priority chunk in `brand_spec_{client_id}` namespace

**Integration points:**
- [ ] PPT Builder: retrieve visual identity summary when selecting template + configuring colors/fonts
- [ ] Slide Content Agent: include layout pattern hints in prompt so copy length matches visual density
- [ ] Upload UI: show extraction progress per slide, display thumbnail grid when done
- [ ] File list: visual_ref files show thumbnail preview instead of just filename

**Infrastructure:**
- [ ] Docker sidecar: LibreOffice headless container for PPTX/PDF → PNG conversion
- [ ] Object storage (S3 or local volume): rendered slide PNGs + thumbnails
- [ ] Celery task: `process_visual_file_task` (separate from text pipeline, higher timeout)
- [ ] Rate limiting: Claude Vision calls batched at 5 slides/request to manage cost

**Scope boundary:**
- This phase handles "understanding and describing" visual style
- Does NOT handle pixel-perfect reproduction in generated PPTs
- python-pptx output is limited to: template selection, color scheme, font choices, layout hints
- If client needs exact visual fidelity, output includes style guide PDF for designer handoff

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

- [x] CI/CD: GitHub Actions (pytest + lint + frontend build → Docker image push)
- [ ] Terraform deployment scripts
- [ ] Health checks and alerting
- [ ] Log aggregation
- [ ] Pinecone index backup strategy
- [ ] MongoDB backup and recovery

> **Note**: CI workflow file exists (`.github/workflows/ci.yml`) with 3 parallel jobs (pytest, lint, frontend build). Docker image push step is defined but not active (needs Docker Hub credentials in repo secrets).

### 3.4 Testing

- [x] Unit tests (53 passing, pure logic + mocked deps)
- [ ] Integration tests: Docker Compose 起全套服务后跑端到端 pipeline
- [ ] Load test: concurrent pipeline runs, budget enforcement under parallelism

### 3.5 Quality of Life

- [ ] More PPT template variants per project type (current ones are placeholders)
- [ ] Client VI color/font customization in PPT Builder
- [ ] Batch operations (run pipeline for multiple projects)
- [ ] PDF export as alternative to .pptx
- [ ] Token refresh interceptor in frontend API client

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

- [x] ~~Visual reference file processing depth~~ → Phase 2.4 Claude Vision pipeline
- [ ] Social media data acquisition compliance (varies by locale)
- [ ] Resource database cold-start strategy
- [x] ~~Resource Agent trigger boundary~~ → Strategy output determines resource types automatically
- [x] ~~Narrative Agent prompt design~~ → Implemented with page-referenced JSON output
- [ ] Client feedback rerun: auto-detect node vs user manual selection
- [x] ~~Initial PPT template count~~ → 4 types planned (social, PR, integrated, brand refresh), not yet created

---

## Phase 1 Remaining Work (Priority Order)

Short list of items checked above that are structurally complete but need finishing:

1. **Budget enforcement in agents** — Add `budget.use_llm_call()` calls in each agent before LLM invocation. Small change, high importance for production safety.
2. **PPT templates** — Create 4 `.pptx` template files with proper slide layouts. Design work, not code.
3. **Three-tier deck structure lookup** — Deck Orchestrator should query project → client → global structure before generating. ~20 lines of code.
4. **Resource Excel import** — Parse uploaded `.xlsx` with openpyxl, create records, embed, upsert to Pinecone. Medium effort.
5. **OAuth token extraction on frontend** — `/login` page needs to read `?token=` from URL params after OAuth redirect. ~10 lines.
