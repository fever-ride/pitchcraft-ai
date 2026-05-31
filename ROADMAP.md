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
- [x] ~~Internal history search via Pinecone (project namespace)~~ → Removed in 3.8 (duplicates Strategy P1's brand RAG)
- [x] Deterministic fallback: Tavily → DuckDuckGo → empty (internal RAG fallback removed in 3.8)
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
- [x] KOL/KOC database with manual entry + Excel bulk import
- [x] Pinecone resource_kol namespace for vector matching
- [x] Trigger logic: activates only when strategy includes social channels
- [x] Clean skip when no external resources needed

### 1.7 Deck System

- [x] Deck Orchestrator: three-tier structure priority (global / client / project)
- [x] Node 3: HITL structure confirmation (add/remove/reorder slides)
- [x] Slide Content Agent: per-page content generation with brand tone enforcement via RAG
- [x] Streaming: push each completed slide to frontend immediately (slide_generated WebSocket event)
- [x] Narrative Agent: non-blocking coherence check, outputs suggestion list with page references
- [x] Node 4: Gallery Review UI (thumbnail nav, preview, narrative panel, batch mark + regenerate)
- [x] PPT Builder: python-pptx template assembly, web preview + .pptx download
- [x] Fixed templates: one per project type (social, PR, integrated, brand_refresh, default)

### 1.8 Stability and Observability

- [x] Request Budget: max 30 LLM calls, 10 search calls, 300s timeout per pipeline
- [x] Fallback chains for each external dependency
- [x] Per-stage metrics collection (stage_metrics MongoDB collection)
- [x] Language Router: detect brief language (Chinese / English), select matching prompt templates


### 1.9 Frontend (Core)

- [x] Login + organization context
- [x] Client management (shared Brand Library)
- [x] Project creation + file upload
- [x] Pipeline execution view with real-time WebSocket updates
- [x] HITL confirmation UIs (Nodes 1-4)
- [x] Gallery Review component (GalleryView, SlideThumbnail, SlidePreview, NarrativePanel)
- [x] PPT preview + download page

> **Note**: Organization context is implicit (derived from JWT). Single-org per user assumed. No org switching UI.

---

## Phase 2: Research and Resource Enhancement

Deeper research, expanded resource types, client feedback loop.

### 2.1 Research Agent Enhancement

- [x] Multimodal competitor analysis (uploaded screenshots → Claude Vision → structured JSON)
- [x] ~~Third-party social data APIs (locale-specific: Chanmama/Feigua for China, CreatorIQ for global)~~ → Removed from Research Agent in 3.8 (KOL profile discovery belongs in Resource Agent; social_data.py module retained for future reuse)
- [x] Richer competitor reports: social_presence, content_trends, risks, recommended_approach
- [x] ~~Locale-aware source selection (auto-detect CN vs global from brief content)~~ → Removed in 3.8 (tied to social data feature)
- [x] API endpoint: POST /research/competitor-screenshots (batch visual analysis)

### 2.2 Resource Agent Expansion

- [x] Media resource database (outlets, journalists, publish types, pricing)
- [x] Vendor database (event companies, photographers, venues)
- [x] Ad placement database (OOH, elevator, magazine, cinema)
- [x] Pinecone namespaces: resource_media, resource_vendor, resource_placement
- [x] Trigger logic expansion: PR → media, offline → vendor, ads → placement
- [x] Multi-type parallel retrieval in resource agent
- [x] Excel import supports all resource types with type-based namespace routing
- [x] Resource model expanded with type-specific fields (outlet_type, beat, service_type, placement_type, etc.)

### 2.3 Client Feedback Loop (Node 5)

- [x] Feedback entry UI: free text + approved/rejected direction tagging
- [x] Feedback persistence to Brand Library (approved directions embedded to brand_spec namespace)
- [x] Targeted rerun: system suggests rerun node based on feedback target, user confirms
- [x] Rerun matrix: strategy / slide / structure / resource level (RERUN_SUGGESTIONS mapping)
- [x] Strategy Phase 2 reads rejected directions from history to avoid repeats
- [x] Executor supports `start_from` parameter for partial pipeline re-execution

### 2.4 Visual Reference Processing

Design decks and moodboards are primarily visual. Text extraction is near-useless for these files. This phase adds a multimodal pipeline that converts visual content into structured style descriptions, then embeds them as text for downstream RAG retrieval.

**Pipeline:**
- [x] PPTX/PDF → per-page PNG rendering (LibreOffice headless + pdftoppm in Docker)
- [x] PNG → Claude Vision analysis (structured style JSON per slide)
- [x] Style JSON → text description → BGE-M3 embedding → Pinecone `brand_spec_{client_id}`
- [x] Batch processing: skip slides with >80% text content (`is_mostly_text` flag)
- [x] Thumbnail storage: save low-res PNGs to /data/thumbnails volume

**Style extraction schema (Claude Vision output per slide):**
- [x] Color palette: primary, secondary, accent, background (hex values)
- [x] Layout pattern: e.g. "full-bleed image", "left-right split", "centered title + subtitle"
- [x] Typography style: serif/sans-serif, weight hierarchy, size contrast
- [x] Image-to-text ratio: percentage estimate
- [x] Visual density: minimal / moderate / dense
- [x] Design keywords: 3-5 descriptors (e.g. "corporate", "playful", "tech-forward")
- [x] Notable elements: icons, charts, illustrations, photography style

**Aggregation (file-level summary):**
- [x] After all slides processed, generate a file-level "Visual Identity Summary"
- [x] Summarize dominant patterns across slides (most frequent layout, consistent colors)
- [x] Store as a single high-priority chunk in `brand_spec_{client_id}` namespace

**Integration points:**
- [x] PPT Builder: visual identity retrievable from brand_spec namespace at generation time
- [x] Slide Content Agent: can retrieve layout hints from brand_spec namespace
- [x] Upload UI: file list shows thumbnail grid + visual summary for visual_ref files
- [x] File list: visual_ref files show expandable thumbnail preview + style description

**Infrastructure:**
- [x] Docker: LibreOffice headless + poppler-utils in backend Dockerfile
- [x] Thumbnail volume: /data/thumbnails mounted in docker-compose
- [x] Celery task: `process_visual_file_task` (separate from text pipeline, time_limit=600s)
- [x] Rate limiting: Claude Vision calls batched at 5 slides/request

**Scope boundary:**
- This phase handles "understanding and describing" visual style
- Does NOT handle pixel-perfect reproduction in generated PPTs
- python-pptx output is limited to: template selection, color scheme, font choices, layout hints
- If client needs exact visual fidelity, output includes style guide PDF for designer handoff

### 2.5 Frontend (Enhanced)

- [x] Node 5: feedback entry + rerun trigger UI (FeedbackPanel component in proposal page)
- [x] Resource library management interface (/resources — list, filter by type, Excel import)
- [x] Research data display with refresh controls (/research — load by pipeline ID, refresh rerun)

### 2.6 Structured Brand Profile

Replaces the unstructured brand_spec Pinecone search as the primary source of brand identity for agents. Brand identity is a single authoritative document, not a corpus to search — storing it in MongoDB and loading directly into prompts is more reliable than vector retrieval.

**Why MongoDB, not Pinecone, for brand identity:**
- BrandProfile is always loaded (no retrieval threshold to miss)
- Structured fields (tone_principles, forbidden_directions) enable hard-constraint checks in brand_check
- No semantic search overhead — full profile is injected directly into the prompt
- Feedback directions accumulate incrementally via `$addToSet` without overwriting the core identity

**Schema (brand_profiles collection):**
```
client_id, org_id (1:1 with clients)
brand_name, positioning, target_audience, competitive_position
personality[]             ← brand personality traits
tone_principles[]         ← communication rules (key signal for brand_check)
forbidden_directions[]    ← brand-spec taboos, set by AE
key_messages[]            ← core points the brand always conveys
approved_directions[]     ← auto-accumulated from client feedback ($addToSet)
rejected_directions[]     ← auto-accumulated from client feedback ($addToSet)
```

- [x] MongoDB collection: `brand_profiles` (one doc per client, upsert pattern)
- [x] Repository: `find_by_client`, `upsert_by_client`, `add_feedback_directions` ($addToSet, no upsert)
- [x] LLM extraction: POST /brand-profile/extract → haiku model → returns draft, does NOT save
- [x] CRUD API: GET/PUT /clients/{id}/brand-profile
- [x] Strategy Phase 1: loads BrandProfile → injects as structured block before Pinecone brand results
- [x] Brand check: prefers BrandProfile if tone_principles or forbidden_directions are set; falls back to Pinecone
- [x] Feedback loop → BrandProfile: approved_directions synced in `embed_feedback_directions`; rejected_directions synced in `submit_feedback` POST handler
- [x] Batch job (`process_unembedded_feedback`): also syncs rejected_directions for pre-existing feedback records
- [x] `format_brand_profile_for_prompt`: distinguishes "Forbidden Directions (from brand spec)" vs "Previously Rejected Directions (from client feedback)" in the prompt block
- [x] Frontend: Brand Profile tab on client page (extract-from-text flow, full form, read-only feedback directions section)

**Agent prompt block format:**
```
[Brand Profile: {brand_name}]
Positioning: ...
Target Audience: ...
Personality: ...
Tone Principles:
  - ...
Forbidden Directions (from brand spec):
  - ...
Previously Approved Directions (from client feedback):
  - ...
Previously Rejected Directions (from client feedback):
  - ...
```

---

## Phase 3: Production Hardening

Version control, analytics, deployment infrastructure.

### 3.1 Version Management

- [x] Auto-save version on each generation or modification (executor saves snapshot on pipeline_complete and rerun)
- [x] Version diff view (what changed between versions) — field-level diff API + frontend side-by-side comparison
- [x] One-click rollback to any previous version (creates new version from old snapshot, updates Redis state)
- [x] Version notes (editable per-version via PUT endpoint)

### 3.2 Analytics Dashboard

- [x] Agent trigger rate and interception rate (resource_agent_trigger_rate + per-stage trigger_count)
- [ ] Brief Analyzer clarification frequency (needs clarification event tracking)
- [ ] Narrative Agent suggestion acceptance rate (needs acceptance event tracking)
- [x] Average pipeline execution time (avg_duration_s from stage_metrics aggregation)
- [x] Request Budget usage distribution (avg_llm_calls, avg_search_calls)
- [x] Cache hit rate (cached_research_entries count from Redis scan)
- [x] Feedback stats: rerun trigger rate, target distribution, direction counts
- [x] Version stats: total versions, rerun count, rollback count, trigger distribution
- [x] Frontend dashboard page (/analytics) with KPI cards, stage bar chart, feedback breakdown

### 3.3 Infrastructure and DevOps

- [x] CI/CD: GitHub Actions (pytest + lint + frontend build → Docker image push)
- [x] Terraform deployment scripts (ECS Fargate + ALB + ElastiCache + ECR + CloudWatch)
- [x] Health checks and alerting (detailed /health/detailed endpoint, Docker healthchecks, CloudWatch alarms)
- [x] Log aggregation (CloudWatch Logs with 30-day retention, per-service log groups)
- [ ] Pinecone index backup strategy
- [ ] MongoDB backup and recovery

> **Note**: CI workflow file exists (`.github/workflows/ci.yml`) with 3 parallel jobs (pytest, lint, frontend build). Docker image push step is defined but not active (needs Docker Hub credentials in repo secrets).

### 3.4 Testing

- [x] Unit tests (105 passing, pure logic + mocked deps)
- [x] Integration tests: Docker Compose E2E (health, pipeline start, status, versions, analytics, files, resources)
- [x] Load test: Locust script for concurrent pipelines, budget enforcement, analytics queries

### 3.5 Quality of Life

- [ ] More PPT template variants per project type (current ones are placeholders)
- [ ] Client VI color/font customization in PPT Builder
- [ ] Batch operations (run pipeline for multiple projects)
- [ ] PDF export as alternative to .pptx
- [x] Token refresh interceptor in frontend API client (auto-refresh on 401, queued retries, redirect to login on failure)

### 3.7 Brief Analyzer Refinement

Schema and retrieval improvements for Brief Analyzer, addressing downstream type safety and retrieval precision.

**Schema improvements:**

- [ ] `category` → Enum (`CampaignCategory`: beauty_launch, tech_launch, fmcg_brand_refresh, luxury_event, food_seasonal, OTHER) + `category_detail: str` fallback for OTHER
  - Enables Campaign KB metadata filter (exact match instead of fuzzy semantic)
  - Enum values derived from Campaign Knowledge Base's `meta.campaign_type` taxonomy
  - JSON Schema `enum` constraint forces LLM to pick from predefined list
- [ ] `budget` → `BudgetRange` nested model (`min_amount`, `max_amount`, `currency`, `raw_text`)
  - Eliminates try/except in Media Planner's `_compute_absolute_budgets()`
  - `raw_text` preserves original brief wording for human review
- [ ] Field `description` enrichment: add boundary cases and fill-rules to each field's Pydantic description (directly improves LLM extraction accuracy via tool schema)

**Campaign KB retrieval redesign:**

- [ ] Two-step retrieval: (1) run basic extraction without campaign context → get `category`; (2) use `category` as metadata filter for precise Campaign KB query
  - Current: blind query before extraction, injects possibly irrelevant context
  - New: category-filtered query returns only same-type historical campaigns
- [ ] Ablation validation: compare `clarification_questions` quality with vs without campaign context on 20 real briefs (blind evaluation by team)
  - If delta is negligible → remove Campaign KB from Brief Analyzer entirely (reduce latency + token cost)
  - If helpful → keep two-step approach

**Frontend UX:**

- [ ] `client_id` input: replace text field with searchable dropdown (existing clients from MongoDB) + "Create new client" option
  - Reduces typo-caused retrieval failures
  - Ensures Pinecone namespace consistency

**Priority order:** category enum → budget struct → frontend dropdown → two-step retrieval → ablation → description enrichment

### 3.8 Research Agent Overhaul

Current Research Agent has structural issues: single query, functional misplacement, dead features, and brittle caching. This section tracks the redesign.

**Remove: Internal RAG** ✅

- [x] Remove `retrieve_for_client()` call from Research Agent
  - Reason: Strategy P1 already searches brand_spec + brand_style + project namespaces; Campaign KB retrieval (Phase 5.6) handles historical case references. Research Agent duplicating this adds noise without value.
  - `internal_references` field removed from ResearchResult schema
  - Fallback chain no longer falls back to internal RAG; returns empty results on web search failure

**Remove/Relocate: Social data (find-KOL logic)** ✅

- [x] Remove `fetch_social_data()` from Research Agent
  - Previous behavior: searched Chanmama/Feigua/CreatorIQ for influencer profiles (followers, engagement_rate) — this is resource discovery, not market research
  - Belongs in: Resource Agent's retrieval phase (or a dedicated social listening module if we later add brand-level SOV/sentiment analysis)
  - `social_data.py` module retained for future use by Resource Agent or a dedicated social listening feature

**Fix: Single query → multi-dimensional search**

- [ ] Replace single `f"{client_name} {theme} marketing campaign competitor"` with LLM-generated query set:
  - Competitor activity: `"{competitor_name} 近期 campaign 2024"`
  - Category trends: `"{category} 行业趋势 {year}"`
  - Platform trends: `"{channel} {category} 爆款内容"` (per channel from brief)
  - Audience behavior: `"{audience} 消费行为 偏好"`
- [ ] Multi-round: after first-pass identifies competitor names, do follow-up searches per competitor
- [ ] Information sufficiency check: LLM self-evaluates whether results are adequate before synthesis

**Fix: Competitor screenshot analysis not wired into pipeline**

- [ ] Wire `competitor_screenshots` into `research_agent_node` from PipelineState
  - Currently: `run_research()` accepts the param but pipeline node never passes it
  - Option A: allow file/image upload at `hitl_brief` node, store in state, pass to research
  - Option B: reference files already uploaded to project namespace (file records in MongoDB)
- [ ] Consider expanding to general "supplementary materials" (competitor PDFs, articles, text notes) — not just screenshots

**Fix: Output consumption by Strategy P2**

- [ ] Replace `json.dumps(research_result)[:3000]` truncation with structured summary
  - Current: downstream sees arbitrary first 3000 chars of a JSON blob
  - Improved: Research Agent outputs a prioritized `executive_summary` (500 tokens max) + full structured data. Strategy P2 reads summary + specific fields it needs (competitors, opportunities)

**Fix: Cache key collision**

- [ ] Cache key uses `search_query[:50]` which can collide across different briefs for same client
  - Fix: hash the full query string (or structured_brief hash) instead of truncating
  - Also: `_make_key` param is named `competitor_name` but receives query text — rename for clarity
  - Consider: cache per-query (multiple keys per pipeline run) instead of caching the entire merged result

**Not yet planned (future consideration):**

- Multi-turn research with iterative deepening (agent decides when to stop)
- Structured competitor comparison matrix output (positioning / pricing / channels / content style)
- Platform-specific trend APIs (Xiaohongshu trending topics, Douyin challenge data)

### 3.6 Cost Optimization

**Prompt Caching (rerun scenario)**
- [ ] Mark stable context (brand specs, system prompts, RAG results) with `cache_control: ephemeral`
- [ ] On rerun, identical prefix hits Anthropic cache → ~90% token cost reduction on stable portion
- [ ] Applicable agents: Strategy P2 (brand_spec RAG), Brand Check (brand_spec RAG), Slide Content (big_idea + brand_direction)

**Fork-mode parallel caching (slide generation)**
- [ ] Refactor Slide Content from sequential `for` loop to parallel `asyncio.gather`
- [ ] All slides share identical prefix: system prompt + big_idea + brand_direction + brand RAG (~5000 tokens)
- [ ] Only per-slide instruction differs (~200 tokens)
- [ ] Fork pattern: 1 full call + (N-1) delta-only calls → 15-slide deck costs ~1 + 14×delta instead of 15×full
- [ ] Requires: messages prefix byte-identical across calls for cache hit

**Narrative Agent co-caching**
- [ ] Narrative Agent runs in parallel with Slide Content, shares same slides context
- [ ] Can cache the full slides array as shared prefix

**Token tracking**
- [ ] Per-agent token usage (input/output) logged in stage_metrics
- [ ] Dashboard shows cost attribution by agent and pipeline
- [ ] Enables informed budget tuning (e.g. lower max_tokens for agents that consistently use less)

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

## Phase 4: Resource Intelligence & Project Archive

Richer resource profiles, knowledge accumulation from completed projects.

### 4.1 Resource Profile Enrichment

- [x] New resource fields: `categories`, `content_style`, `audience_tags`, `past_cpe`
- [x] Free-text, no standardization needed (semantic matching handles synonyms like "cosmetics" ≈ "beauty")
- [x] Supported in both Excel bulk import AND manual single-entry API (`POST /resources`)
- [x] New fields concatenated into embedding text for semantic similarity — NOT metadata filter
- [x] Metadata filter remains for discrete enums only: status, platform, type
- [x] Brief Analyzer adds `category` field (project classification, e.g. "beauty new product launch")
- [x] Strategy P2 adds `content_tone` field (e.g. "playful", "professional")
- [x] Resource Agent query construction: `big_idea + content_tone + audience_insight + category` → semantic query; `status + platform` → metadata filter
- [x] Chinese header alias mapping for Excel import (25+ CN-to-EN column mappings)
- [x] Import result feedback: recognized_columns + ignored_columns returned to user
- [x] Manual resource creation also upserts to Pinecone (searchable immediately)

### 4.2 Project Archive Pipeline

- [x] New API: `POST /api/v1/projects/{id}/archive` (upload recap/case study)
- [x] LLM structured extraction from one report → multi-destination:
  - Resource performance data → update `collaboration_history`, refresh resource embedding
  - CampaignRecord → MongoDB `campaign_records` (pending confirmation → proposition indexing on confirm)
- [x] Built on existing file upload + RAG pipeline, extended with extraction + routing
- [x] `GET /api/v1/projects/{id}/archive` to check extraction status and results

> **Phase 5 migration complete:** `_distribute_to_brand_style()` has been removed from archive pipeline (code-confirmed clean 2026-05-29: zero occurrences in `backend/`). Strategy learnings and audience insights now route exclusively through CampaignRecord → proposition indexing → `campaign_knowledge_{org_id}`. The `brand_style_{client_id}` namespace is now sourced only by Pipeline 1 (Brand Library uploads: `BRAND_HISTORY_PROPOSAL`, `BRAND_HISTORY_COPY`) — it stores copywriting tone/style reference text, not strategy content.

### 4.3 Progressive Resource Accumulation

- [x] Post-pipeline: auto-record which resources were selected + project category
- [x] Reverse-tag resources with confirmed categories from actual usage (`$addToSet`)
- [x] Resource profiles improve over time without manual maintenance

### 4.4 External Data API (Interface Only)

- [x] Config: `social_data_provider` field reserved
- [x] Resource model has `followers_count`, `engagement_rate` fields ready for external data
- [ ] Abstract base: `backend/core/integrations/social_data.py`
- [ ] Adapter interface: `fetch_profile(platform, handle) -> dict`
- [ ] Suitable for: periodic followers_count / engagement_rate refresh
- [ ] Candidate providers: Xinbang, Chanmama, Huitun (evaluate on demand)
- [ ] Not a core dependency — data supplement only

### 4.5 RAG Pipeline Quality Improvements

Three low-cost improvements to the existing document ingestion pipeline. Benefits all downstream agents (Strategy, Brand Check, Slide Content, Research) immediately.

**4.5.1 Contextual Embedding**

Prepend document metadata before embedding so the vector captures source context, not just content.

```
Current:  "Brand tone should remain youthful and energetic..." → embed
Improved: "[BrandX | brand_spec | brand_guidelines_2025.pdf | Tone of Voice]
           Brand tone should remain youthful and energetic..." → embed
```

- [x] Prefix format: `[Client | file_type | filename | section/page]`
- [x] PDF: include page number in prefix
- [x] PPTX: include slide index in prefix
- [x] Migration script for existing vectors (`scripts/migrate_vectors.py` with --dry-run support)

**4.5.2 Source Location Tracking**

Store page/slide position in Pinecone metadata for citation traceability.

- [x] PDF chunks: `page_number` in Pinecone metadata
- [x] PPTX chunks: `slide_index` in Pinecone metadata
- [x] `filename` stored in Pinecone metadata for all chunks
- [x] RAGResult exposes `source_location` property (e.g. "brand_guidelines.pdf, page 3")
- [x] Agents receive cited context via `format_results_with_sources()` (Strategy, Research, Deck agents updated)
- [ ] HITL UI displays source citations alongside RAG-sourced content (frontend)

**4.5.3 Adaptive Chunking by File Type**

Different document types have different information density. Adjust chunk parameters accordingly.

| file_type | chunk_size | overlap | Rationale |
|-----------|-----------|---------|-----------|
| brand_spec | 800 | 200 | Rule-dense, every sentence matters |
| brand_style | 1200 | 300 | Proposals/decks, longer narrative context for tone reference |
| project_brief | 600 | 100 | Short, focused documents |
| competitor_copy | 1000 | 200 | Articles, moderate density |

- [x] Define chunk profiles as config dict keyed by file_type (`CHUNK_PROFILES` in chunker.py)
- [x] Chunker selects profile based on file record metadata
- [x] Unknown types fall back to current default parameters (512 tokens, 64 overlap)

**4.5.4 Document Cleaning**

Low-cost noise removal applied before chunking. Targets the most common quality issues in internal business documents (brand specs, decks, recap reports).

*Boilerplate / header-footer removal (PDF only):*
- [x] Lines appearing on >30% of pages are detected as boilerplate and stripped (company names, confidentiality notices repeated on every page)
- [x] Page-number patterns removed: handles both Chinese (`第 3 页`, `第3P`) and English (`Page 3`, `3 / 20`, bare numerals) formats
- [x] Detection uses normalised line-level frequency across all pages; single-page documents skipped

*Minimum chunk token threshold:*
- [x] Chunks below 20 tokens discarded after splitting (covers section headers, stray labels, single-word fragments that add no retrieval value)
- [x] Threshold constant `MIN_CHUNK_TOKENS = 20` in `chunker.py`

*Language note:* Chinese business documents routinely mix Chinese prose with English industry terms (KOL, ROI, CPE, TVC, OOH). Cleaning preserves all English terms as-is; only structural noise (page numbers, repeated headers) is removed.

---

## Phase 5: Campaign Knowledge Base

Upgrade archive pipeline from fragmented text chunks into a structured, multi-layered knowledge system. Every agent in the pipeline benefits from historical campaign data. This phase establishes the data foundation that Phase 6 (Media Planning Intelligence) depends on.

### Why this matters

Most RAG systems store raw text chunks and retrieve by semantic similarity. This returns "similar words" but not "decision logic from similar situations." The difference:

```
Shallow RAG:
  "This campaign used 10 KOLs on Xiaohongshu..." (text fragment)
  → Agent sees words but not WHY or WHETHER it worked

Structured knowledge RAG (this phase):
  Campaign Record → Proposition: "[beauty | launch | 2M] KOC tier at 10% budget drove 60% engagement"
  → Agent sees: what was decided, under what conditions, and what the outcome was
  → Agent can reason: "similar conditions to ours, this allocation pattern worked"
```

The competitive moat is not the retrieval technology. It is the accumulated structured decision records that improve with every archived campaign. After 20+ campaigns, the system's recommendations are informed by real outcome data specific to this agency's clients and industry verticals.

### 5.1 Knowledge Architecture

**Design principle:** Start from what agents need at generation time, not from what data is available.

**Full knowledge system (five layers):**

```
Layer                        Role              Implementation              Status
─────────────────────────────────────────────────────────────────────────────────────
Brand Library                Constraint        MongoDB + Pinecone vectors  Implemented
Campaign Knowledge Base      Reference         MongoDB + Pinecone props    This phase
Methodology Library          Guidance          —                           Not in v1 scope (Phase 5.9+)
Industry Knowledge           Context           Real-time search + cache    Implemented
Resource Library             Execution pool    MongoDB + Pinecone vectors  Implemented
```

Three layers have dedicated storage (Brand Library, Campaign Knowledge Base, Resource Library). Industry Knowledge is served by Research Agent's real-time search with 30-day semantic caching. **Methodology Library is out of v1 scope** — see Phase 5.9 for the design plan.

**This phase builds Campaign Knowledge Base.** The other layers are already operational.

**Campaign Knowledge Base vs Brand Library boundary:**

```
Brand Library (already implemented)
  = Brand identity. What this brand IS.
  = Constraint: agents cannot violate.
  Stores: brand specs, visual identity, copywriting style examples, approved directions
  Scope: per-client, relatively static
  Namespace: brand_spec_{client_id}, brand_style_{client_id}

Campaign Knowledge Base (this phase)
  = Project experience. What was DONE and whether it WORKED.
  = Reference: agents can learn from but are not bound by.
  Stores: structured decision records (strategy, media plan, execution, outcomes)
  Scope: org-wide cross-client retrieval (desensitized), accumulates with every project
  Storage: MongoDB campaign_records + Pinecone campaign_knowledge_{org_id}
```

**Boundary rule:** If the information retains value regardless of wording (numbers, decisions, outcomes), it belongs in Campaign Knowledge Base. If the value IS the wording (tone, phrasing, narrative style), it belongs in Brand Library.

**Cross-client retrieval design:**

```
Storage:   each CampaignRecord belongs to a client_id (clear data ownership)
Retrieval: matches by industry + campaign_type + budget_tier across all clients in the org
Response:  desensitized (no client_name, only meta + decisions + outcomes)
Optional:  admin can mark records as "client_only" (isolate competing brands)
```

This enables faster accumulation. A beauty launch for Client A informs planning for Client B's beauty launch.

**Privacy limitation (known, acceptable for current scope):**

Removing `client_name` is necessary but not sufficient for full anonymization. A combination of industry + budget_tier + target_audience can be re-identifying in niche markets (e.g. "automotive, 50M budget, new energy, family" narrows to very few brands in China). Current desensitization is adequate for single-agency internal use where all users already have access to all client work. For multi-agency SaaS or external licensing of campaign data, stronger measures would be needed:
- Budget ranges instead of exact figures (already using tiers, not exact numbers)
- Generalized audience descriptions ("young female" not "Gen-Z female in tier-1 cities aged 18-24")
- Minimum k-anonymity check before cross-client retrieval returns a record
- Opt-in per client: client onboarding includes consent for anonymized cross-reference

These are not implemented now. The current design prioritizes knowledge accumulation speed for a single agency deployment.

**Two layers within Campaign Knowledge Base:**

```
Layer 1: Structured CampaignRecord (this phase)
  MongoDB campaign_records collection + proposition vectors in Pinecone
  Used for: finding similar past campaigns, referencing specific decisions and outcomes
  Consumers: all pipeline agents (each reads different fields)

Layer 2: Distilled insights (Phase 5.9, feeds back into Methodology Library)
  MongoDB media_insights collection
  Used for: cross-campaign patterns, industry benchmarks
  Trigger: auto-distillation when a client accumulates 10+ confirmed records
```

### 5.2 CampaignRecord Schema Design

Each archived project produces one structured record. Fields organized by five knowledge dimensions, each consumed by different agents:

```
CampaignRecord:
  meta:                              ← used for retrieval matching (all agents filter by this)
    campaign_type                      (launch / branding / conversion / event / crisis / always_on)
    industry                           (beauty, automotive, tech, F&B, fashion, ...)
    budget_tier                        (under_100k / 100k_500k / 500k_2m / 2m_5m / above_5m)
    target_audience_summary            (one-line description)
    duration_days                      (campaign length)
    channels_used[]                    (xiaohongshu, douyin, weibo, pr, event, ...)
    client_name                        (LLM-extracted brand/advertiser name from document, e.g. "安踏"; not a DB FK — the real FK is campaign_records.client_id, passed from project context by archive_process.py)

  strategy_decisions:                ← Strategy P2 references ("what direction was chosen and why")
    industry_insight
    audience_insight
    strategy_framework
    big_idea
    big_idea_rationale
    positioning
    rejected_directions[]:             (structured, not parallel lists)
      direction                        (the direction name)
      reason                           (why it was dropped, optional)

  communication_plan:                ← Strategy P2 + Deck Orchestrator ("how to fight")
    channel_mix[]:                     (strategic channel roles, NOT media buying)
      channel
      channel_type                     (social / offline / pr / paid)
      role                             (引爆/种草/转化/沉淀 or ignite/seed/convert/sustain)
      content_direction
      target_audience_segment
    phasing_structure                  (phase pattern, e.g. "三阶段：预热/引爆/长尾" — vectorized)
    phasing_rhythm                     (tempo logic, e.g. "首波引爆后5-7天跟进第二波" — vectorized)
    cross_platform_logic               (how channels interact)
    content_themes[]                   (thematic pillars across channels)

  media_plan:                        ← Media Planning Agent ("what to buy and how much to spend")
    total_media_budget
    channel_budget_split{}             (channel -> amount or percentage)
    tier_breakdown[]:                  (only paid/purchased resources)
      tier                             (top / mid / tail / koc / media)
      platform
      count
      budget_allocated                 (at least one of budget_allocated / budget_percentage required)
      budget_percentage                (validator sets budget_missing=true if both null)
      role                             (awareness / amplification / ugc / credibility)
      selection_criteria               (why this tier got this allocation)
    rationale                          (overall media plan reasoning)

  execution:                         ← Resource Agent ("how it was actually done")
    resources_used[]:
      name
      type                             (kol / koc / media / vendor)
      tier
      platform
      cost
      deliverables                     (post count, content type)
    content_formats[]                  (video, carousel, article, live stream)
    vendors_used[]
    actual_timeline[]                  (concrete execution dates — MongoDB only, NOT vectorized)

  client_learnings:                  ← Brief Analyzer references ("how this client decides")
    decision_style                     (e.g. "偏保守，需要数据支撑")
    client_approved_directions[]       (directions client explicitly approved)
    client_rejected_directions[]       (directions client explicitly vetoed)
    kpi_priorities[]                   (KPIs client cares most about, in priority order)
    communication_notes                (how to communicate with this client)

  deck_info:                         ← Deck Orchestrator references
    slide_count
    chapter_structure[]                (section titles in order)
    presentation_style                 (data-heavy, visual, storytelling)

  outcome:                           ← all agents reference ("what happened"; campaigns only)
    kpi_results{}                      (metric -> actual value)
    best_performing_tier
    best_performing_channel
    underperforming_areas[]
    lessons_learned[]                  (project-specific takeaways)
    reusable_insights[]                (transferable patterns for other projects)
    overall_rating                     (1-5 scale, set during human confirmation)

  metadata:
    record_type                        (proposal / campaign) — see note below
    pitch_outcome                      (won / lost / unknown) — proposals only, set manually at confirmation
    status                             (pending_confirmation / confirmed)
    confidence                         (high / partial / low, based on source data completeness)
    source_archive_id                  (link back to raw archive upload)
    created_at
    confirmed_by                       (user who reviewed and confirmed)
    confirmed_at
```

**record_type design:**

The same schema handles both proposal decks and recap reports. `record_type` distinguishes them:

```
record_type = "proposal"
  → extraction covers: meta, strategy_decisions, communication_plan, deck_info
  → outcome / execution fields are empty (not yet run)
  → pitch_outcome: won / lost / unknown (set manually at confirmation)

record_type = "campaign"
  → full extraction: all dimensions including execution and outcome
  → pitch_outcome: not applicable (always "unknown")
```

The product output IS a proposal. Past proposals are the most directly relevant reference — they show what strategic thinking won client approval. Campaign records provide outcome validation. Both are needed; agents weight them differently by profile.

**client_learnings — manual input only:**

`client_learnings` fields are NOT extracted by LLM. Recap reports contain formal KPI data, not informal notes about a client's decision style. This knowledge lives in the AE's memory. The confirmation UI provides a dedicated section for AEs to fill these fields manually after reviewing the extracted record.

**Communication vs Media distinction:**
- Communication plan = strategic ("怎么打"): channel roles, content direction, phasing, cross-platform interaction
- Media plan = tactical ("买什么花多少"): budget allocation, tier breakdown, only paid/purchased resources
- Example: offline event as a communication touchpoint (brand event in launch phase) → communication_plan. Offline event as a purchased venue/media slot → media_plan.

All fields are optional. LLM extracts what it can. User confirms and fills gaps.

**Language note:** Schema field values are stored in whatever language the source document uses (Chinese, English, or mixed). LLM prompts are bilingual (zh/en); language is auto-detected per document via `detect_language()`. Industry terms that are conventionally English even in Chinese documents (KOL, ROI, CPE, KOC, OOH) are preserved as-is.

Implementation: `backend/core/models/campaign_record.py`

### 5.3 Extraction Pipeline (extends existing archive)

```
Current flow (unchanged):
  upload → parse → extract_archive() → ArchiveExtraction
    → _distribute_to_resources() (collaboration_history updates)

New parallel flow (added):
  upload → parse → extract_campaign_record() → CampaignRecord
    → _store_campaign_record() → MongoDB campaign_records (status: pending_confirmation)
    → After human confirmation: proposition extraction → Pinecone campaign_knowledge_{org_id}
```

Note: `_distribute_to_brand_style()` has been removed. All agents now query `campaign_knowledge_{org_id}` namespace via per-agent retrieval profiles (5.6 complete). The `brand_style` namespace is now sourced only by Pipeline 1 Brand Library uploads (copywriting tone/style reference).

**Three parallel LLM extraction calls** (split by information distribution in reports):

```
Call 1: ExtractionBackground (meta + strategy_decisions + communication_plan + deck_info)
  → Text window: first 40,000 chars (strategy is front-loaded in most reports)
  → Role: 资深campaign分析师 / senior campaign analyst
  → Focus: "what direction was chosen and why" + "how to fight"

Call 2: ExtractionExecution (media_plan + execution)
  → Text window: first 40,000 chars (budget tables and execution details are in the first half)
  → Role: 资深整合营销执行专家 / senior integrated marketing execution expert
  → Focus: paid media procurement (KOL/KOC tiers, budgets) + all other execution activities
  → Scope: advertising campaigns (media_plan-heavy), PR campaigns (activities-heavy), or mixed
  → execution.activities: PR events, press conferences, offline activations, UGC campaigns —
    anything that is NOT paid media procurement

Call 3: ExtractionOutcome (outcome only — no client_learnings)
  → Text window: last 20,000 chars (KPI results and retrospectives are back-loaded)
  → Role: 资深campaign评估专家 / senior campaign evaluation expert
  → Focus: "what happened" + "what to learn"
  → Fallback: if key outcome fields are empty AND report is long enough to have a skipped
    middle section, retry once with the preceding 20,000-char section

Merge: results combined, confidence = min(call1, call2, call3)
Partial failure: if one call fails, others still contribute (graceful degradation)
```

**client_learnings excluded from extraction:**
Recap reports contain formal KPI data, not informal notes about a client's decision style. Attempting LLM extraction of client_learnings from a report produces generic or fabricated content. These fields are filled manually by the AE at the confirmation step.

**Why 3 calls instead of 1:**
- Information distribution: strategy in early pages, execution in mid-section, results at the end. A single call must attend to all sections simultaneously.
- Schema complexity: CampaignRecord has 50+ fields across 5 dimensions. Single-call structured output degrades in quality past ~30 fields.
- Prompt specialization: each call gets a domain-specific role and text window optimised for where that information lives in the document.

**Language adaptation:**
All three prompts are bilingual (zh/en dict). Language is auto-detected once per document via `detect_language()` and applied to all three calls. Mixed-language content (Chinese reports with English terms like KOL, ROI, CPE) is handled naturally — Chinese prompts accept and preserve English industry terms in output fields.
- Parallel execution: 3 concurrent calls complete faster than 1 serial call with 3x the output.

Implementation: `backend/core/agents/campaign_extract.py`

**Confirmation API endpoints:**

```
GET  /api/v1/campaigns          — list records (filter by client_id, status)
GET  /api/v1/campaigns/pending  — records awaiting confirmation
GET  /api/v1/campaigns/search   — metadata-based search (confirmed records only)
GET  /api/v1/campaigns/:id      — single record for review
PUT  /api/v1/campaigns/:id/confirm — human confirms, optionally applies edits
```

Implementation: `backend/api/v1/endpoints/campaigns.py`
- Fields not found in source are left null, not hallucinated

**Visual style extraction (PPTX archives only) — DEFERRED, optional:**

Writing "reuses Phase 2.4 pipeline" understates the complexity. Actual requirements:
- PPTX → PNG rendering (LibreOffice headless, already in Docker but slow for 20+ pages)
- Per-page Claude Vision calls (cost: ~$0.01-0.03 per page, 20-page deck = $0.20-0.60 per archive)
- Style JSON → standardized `color_palette[]`, `typography_style` fields (output stability not guaranteed across runs)
- Aggregation logic to merge per-page styles into a file-level summary

Phase 2.4 already does this for brand_spec uploads (stores as text description in Pinecone). But Campaign Knowledge Base needs structured JSON fields, not text embeddings. Adapter work is non-trivial.

**Decision:** Defer visual_style extraction from CampaignRecord v1. The `deck_info.visual_style` field exists in the schema but is populated only when budget/priority justifies it. First iteration focuses on text-extractable fields (chapter_structure, slide_count, presentation_style). Visual style can be added later as an optional enrichment step.

- [ ] (Optional, low priority) Adapt Phase 2.4 output to write structured JSON into CampaignRecord.deck_info.visual_style
- PDF reports skip this step entirely (text-heavy, no design value)

### 5.4 Human Confirmation Step

Extracted CampaignRecord is not immediately available for retrieval. Requires user review.

- [x] `GET /api/v1/campaigns/{id}`: returns extracted record for confirmation UI
- [x] `PUT /api/v1/campaigns/{id}/confirm`: user submits corrections, sets overall_rating, confirms
- [x] Status flow: `pending_confirmation` → `confirmed` (only confirmed records are retrievable)
- [x] On confirmation: triggers background proposition indexing (5.5) automatically
- [x] UI: campaign list page (pending/all tabs), detail page with module-by-module editable form
- [x] Low-confidence records show warning banner, confidence badge on list and detail views
- [x] `pitch_outcome` selector on confirmation page (won / lost / unknown) — proposals only; defaults to unknown; sets retrieval priority signal
- [x] `client_learnings` manual input section on confirmation page — AE fills post-hoc; not LLM-extracted
- [ ] UX polish: guided wizard flow, inline field-level confidence indicators

### 5.5 Proposition Indexing & Contextual Embedding

Standard approach: embed one summary per campaign record. Problem: a single summary embedding dilutes specific decision signals. "Beauty launch, KOC outperformed mid-tier" is lost inside a 200-word summary.

**Proposition extraction (after human confirmation):**

Each confirmed CampaignRecord is decomposed into atomic, self-contained insights:

```
CampaignRecord (beauty launch, 2M budget) → atomic propositions:

- "Beauty launch campaign with 2M budget: top-tier KOL allocated 40% for topic creation, ROI 1.8x"
- "Beauty launch campaign with 2M budget: mid-tier KOL on Xiaohongshu outperformed Douyin by 2x ROI"
- "Beauty launch campaign with 2M budget: KOC tier (50 creators) drove 60% of total engagement at 10% budget"
- "Beauty launch campaign with 2M budget: big idea 'Break the Routine' tested well with Gen-Z female"
- "Beauty launch campaign with 2M budget: 12-slide deck, storytelling structure, opened with market tension"
```

Each proposition is:
- Self-contained (no pronouns, no "the campaign" references)
- Prefixed with campaign meta for contextual embedding (industry + type + budget baked into the vector)
- Linked back to source campaign_record_id for parent retrieval
- Tagged with module origin (strategy_decisions / media_plan / execution / deck_info / outcome)

- [x] LLM-based proposition extraction from confirmed CampaignRecord (8-15 atomic propositions per record)
- [x] Each proposition stored in MongoDB `campaign_propositions` collection with campaign_record_id back-reference
- [x] Each proposition embedded with meta prefix (contextual embedding) and upserted to `campaign_knowledge_{org_id}` Pinecone namespace
- [x] Metadata on each vector: campaign_record_id, campaign_type, industry, budget_tier, **record_type**, **pitch_outcome**
- [x] Fallback: if proposition extraction fails, embed full module text with meta prefix

**Language note:** Propositions are generated in the language of the source document (zh or en). The proposition prompt is bilingual; language is auto-detected. Propositions from Chinese documents contain Chinese text with embedded English terms (KOL, ROI, etc.) preserved as-is — this is intentional, as mixed-language propositions match better against real queries from Chinese-speaking users who naturally mix languages.

**Why contextual embedding matters:**

Without context prefix:
```
"KOC tier drove 60% of engagement at 10% budget"
→ embedding captures the fact but not WHEN this is applicable
```

With context prefix:
```
"[beauty | launch | 2M | Gen-Z female] KOC tier drove 60% of engagement at 10% budget"
→ embedding captures both the fact AND its applicability conditions
```

This means a query "beauty launch KOC effectiveness" matches strongly, while "automotive branding KOC" does not, even though both mention KOC.

### 5.6 Retrieval Design (Parent-Child Pattern)

**Two-level retrieval: propositions for matching, full modules for context.**

Searching propositions gives precision. But agents need full context to make decisions. Solution: retrieve at proposition level, expand to parent module level before sending to LLM.

```
Step 1: Metadata filter on propositions
  campaign_type = "launch", industry = "beauty", budget_tier = "500k_2m", status = "confirmed"

Step 2: Semantic similarity on proposition embeddings
  query: "Gen-Z skincare launch, social-first, authentic tone"
  → cosine similarity against proposition vectors
  → top 10 propositions matched

Step 3: Deduplicate by campaign_record_id
  → 10 propositions may come from 3 distinct campaigns

Step 4: Fetch full modules from MongoDB
  → For each matched campaign, load the modules relevant to the requesting agent
  → Return structured CampaignRecord fields, not raw text

Step 5: Assemble agent context
  → Agent receives: 3 similar campaign records with full relevant modules
  → Plus: the specific propositions that triggered the match (for transparency)
```

**Per-agent retrieval profiles:**

| Agent | Profile | top_k propositions | Modules returned | Rerank |
|-------|---------|-------------------|-----------------|--------|
| Strategy P2 | `strategy_reference` | 6 | strategy_decisions, communication_plan, outcome | No |
| Media Planning | `media_planning` | 15 | media_plan, execution, outcome | Yes (planned) |
| Resource Agent | `resource_reference` | 8 | execution, outcome | No |
| Deck Orchestrator | `deck_reference` | 4 | deck_info, communication_plan | No |
| Brief Analyzer | `brief_reference` | 4 | client_learnings, meta | No |

- [x] Define retrieval profiles as config (top_k, module whitelist, score_threshold)
- [x] Profile auto-selected based on calling agent via profile_name parameter
- [x] Strategy P2 integrated: queries campaign_knowledge, appends historical context to prompt
- [x] `format_campaign_context()` serializes matched records into agent-consumable text
- [x] `org_id` threaded from JWT → PipelineState → agent calls → retriever namespace
- [x] Resource Agent integrated: queries campaign_knowledge with "resource_reference" profile
- [x] Deck Orchestrator integrated: queries campaign_knowledge with "deck_reference" profile
- [x] Brief Analyzer integrated: queries campaign_knowledge with "brief_reference" profile
- [x] **Same-project deduplication**: if both proposal and campaign for the same `project_id` are retrieved, campaign is returned as primary; proposal is demoted to secondary with note "同一项目已有结案数据，此提案仅供策略思路参考，数字为预估值"
- [x] **Context headers label source type**: `[历史结案: ...]` / `[历史提案·中标: ...]` / `[历史提案·未中标: ...]` / `[历史提案·结果未知: ...]` — agents receive clear provenance signal without relying on prompt instructions
- [x] Lost proposals labeled `[历史提案·未中标]` with note "未中标方案，可作为对比参考"
- [ ] Media Planning profile uses cross-encoder rerank (heavier but highest precision needed)
- [ ] Media Planning agent integrated (blocked on Phase 6 Media Planning Agent)
- [ ] Rerank implementation for media_planning profile

**Per-agent profile × record_type guidance:**

| Agent | Proposal | Campaign |
|---|---|---|
| Strategy P2 | ✅ strategy thinking, big idea | ✅ validated strategy + outcome |
| Deck Orchestrator | ✅ primary — pitch structure reference | ⚠️ secondary — recap structure differs from pitch |
| Media Planning | ⚠️ estimated budgets only, not validated | ✅ primary — real allocation + outcome data |
| Resource Agent | ⚠️ proposed resources, may not have been used | ✅ actual resources used + performance |
| Brief Analyzer | ✅ client_learnings (manual), meta | ✅ client_learnings (manual), meta |

**Language note:** Retrieval queries are typically generated by agents in Chinese (or mixed zh/en). `detect_language()` selects the verification prompt language. Pinecone semantic search handles cross-language matching naturally — a Chinese query will match Chinese propositions with embedded English terms (e.g. "KOC tier 效果" matches "[美妆 | launch] KOC tier drove 60% engagement").

Implementation: `backend/core/rag/campaign_retriever.py`

**Hybrid search (keyword + semantic):**

Pure semantic search can miss exact terms (specific budget numbers, platform names, campaign types). Add keyword layer:

- [ ] BGE-M3 sparse vectors stored alongside dense vectors in Pinecone (already supported by our embedding model)
- [ ] Weighted fusion: 0.2 sparse (keyword) + 0.8 dense (semantic) for campaign proposition retrieval
- [ ] Sparse component catches exact industry terms, budget figures, platform names that semantic search may fuzz over

### 5.7 Retrieval Quality Feedback

Track whether retrieved campaign records actually help agents produce better output.

**Implicit signal: HITL modification rate.**

```
Media Planning Agent retrieves 3 historical campaigns → produces media plan
  → User at HITL:
    - Confirms with minimal edits → retrieved campaigns were helpful (positive signal)
    - Heavily rewrites the plan → retrieved campaigns may have been irrelevant (negative signal)
    - Adds budget numbers agent missed → campaigns were relevant but incomplete (neutral)
```

- [ ] Track edit distance between agent output and user-confirmed output at each HITL checkpoint
- [ ] Associate edit distance with the campaign_record_ids that were in the agent's context
- [ ] Aggregate per-record: campaigns that consistently lead to heavy edits get lower quality scores
- [ ] Quality score influences retrieval ranking (higher quality records ranked above lower quality ones with same similarity score)
- [ ] Dashboard: show which campaign records are "high value" (frequently referenced, low edit rate) vs "low value" (referenced but always overridden)

**Explicit signal (optional, low priority):**

- [ ] After HITL confirmation, optional one-click "Were the historical references helpful?" (yes/no)
- [ ] Simpler than edit distance tracking but requires user action

### 5.8 Self-Verification (retrieval sufficiency check)

Prevent agents from blindly using irrelevant historical data. Critical when the knowledge base is sparse (first 5–10 records): Pinecone always returns top-k matches regardless of actual relevance, so without a quality gate the weakest early records would be cited as reference for every new project.

- [x] After retrieval, LLM judges: "Are these historical campaigns similar enough to inform the current plan?" (sufficient / partial / insufficient)
- [x] Criteria: match on at least 3 of — industry, campaign type, budget tier, target audience → sufficient; 2 → partial; <2 → insufficient
- [x] If sufficient: agent uses full retrieved context
- [x] If partial: context returned with `sufficiency_note` injected into formatted output ("参考局限: ..."); agents read this note and adjust confidence accordingly
- [x] If insufficient: returns empty list; agent falls back entirely to prompt-embedded industry knowledge; no historical references cited
- [x] Verification failure (LLM error / timeout): returns original results unfiltered — verification is best-effort, not a hard gate
- [x] Prevents: retrieving a beauty branding campaign and citing it as reference for a tech product launch just because both mention "年轻用户"

Implementation: `verify_retrieval_sufficiency()` in `backend/core/rag/campaign_retriever.py`

**Language note:** Verification prompt is bilingual (zh/en). Language detected from the query string. Matching criteria are language-agnostic (comparing structured meta fields, not text). A Chinese query against Chinese propositions works identically to an English query against English propositions.

### 5.9 Distilled Insights (Methodology Library)

**Not in v1 scope. Design recorded here for future reference.**

---

#### 背景：为什么这是一个单独的层

Campaign Knowledge Base 的 propositions 是**个案事实**：安踏这次奥运营销用了多少 KOL、ROI 是多少。

Methodology Library 要存的是**跨案例规律**：美妆行业新品上市，KOC 层级的 ROI 在统计上持续高于头部。

两者不可互相替代：
- 用个案事实做方法论会导致过拟合（"上次安踏这样做有效"不等于"同类项目都该这样做"）
- 用模糊方法论替代个案引用会失去情境（"KOC 一般更好"比不上"安踏这个预算级别的运动品牌这样做过"）

#### 行业背景

业界讨论的"蒸馏 skill"有三种含义：
1. **模型蒸馏**：大模型生成训练数据 → 微调小模型（知识进权重）
2. **Agent skill 积累**（Voyager 式）：Agent 解决子问题 → 解法写入 skill library → 检索复用（知识进数据库）
3. **人类专家知识结构化**（"蒸馏同事"）：专家大量解题并出声思考 → LLM 提炼决策模式为可检索规则

我们这个 Phase 5.9 属于第 2+3 类混合：从大量 confirmed records（集体过往经验）中提炼跨项目规律，存入可检索数据库，注入 agent prompt。不改模型权重，结果可读可改可审计。

#### 蒸馏对象和去向

| 蒸馏内容 | 来源 | 存入 | 注入给谁 |
|---------|------|------|---------|
| 渠道层级分配规律（某行业 KOC 建议占比） | campaign_records.media_plan + outcome | `media_insights` collection | Media Planning Agent |
| 客户决策风格规律（保守型客户需要数据背书） | campaign_records.client_learnings | `media_insights` collection | Brief Analyzer |
| 策略方向成功率（某类 big idea 在某行业接受率高） | campaign_records.strategy_decisions + pitch_outcome | `campaign_insights` collection | Strategy Phase 2 |

**示例蒸馏输出：**
```
[美妆 | 新品上市 | 100万-500万]
在 6/8 条 confirmed records 中，小红书 KOC 层级（1-5万粉）
是 best_performing_tier，建议预算占比 25-30%
```

#### 触发条件

不是"总记录数"，而是**同一 industry + campaign_type 组合下**：
- ≥8 条 confirmed records
- 其中 ≥5 条有 outcome 数据（无结果的案例蒸馏不出成败规律）

在这之前，Phase 5.9 的功能由 Campaign KB 的命题检索本身承担——agent 从 3 条相关 campaign 的命题里自己推断规律，比预蒸馏的泛化结论更情境化。

#### Checklist（待做）

- [ ] `media_insights` MongoDB collection 设计（tagged by industry + campaign_type + budget_tier）
- [ ] `campaign_insights` MongoDB collection 设计
- [ ] Distillation batch job：跨 records 的 LLM 聚合 call，产出结构化 insight
- [ ] 触发机制：archive pipeline 确认后检查是否达到 threshold，达到则入队
- [ ] Media Planning Agent：从 `media_insights` 检索相关 insight，注入 prompt
- [ ] Strategy Phase 2：从 `campaign_insights` 检索相关 insight，注入 prompt
- [ ] 置信度标注：每条 insight 记录来源 record 数量，agent 能看到"基于 8 条记录"
- [ ] 过期/更新机制：新 record 确认后，已有 insight 标为 stale，下次蒸馏时更新

### Design Decisions

**Decided:**
- Cross-client retrieval: org-wide by default. Records belong to client_id (ownership) but retrieval matches across all clients by industry + campaign_type + budget_tier. Agent responses are desensitized (no client_name). Admin can mark records "client_only" for competing brand isolation.
- Knowledge boundary: Brand Library stores brand identity (constraints, style). Campaign Knowledge Base stores project experience (decisions, outcomes). Boundary rule: if value survives rewording, it is Campaign Knowledge Base. If value IS the wording, it is Brand Library.

**Decided (this session):**
- Extraction reliability: 3 parallel LLM calls (Background/Execution/Outcome), each specialized. Graceful degradation on partial failure. Overall confidence = min of three.
- Proposition granularity: 8-15 per record. LLM instructed to produce self-contained atomic propositions with meta prefix.
- Cold start: agents receive empty campaign context and work normally from prompt-embedded knowledge. No degradation — `if not campaign_context` simply skips the context section.
- Transition cleanup: `_distribute_to_brand_style()` removed from archive pipeline. `brand_style` namespace now sourced only by Pipeline 1 (Brand Library uploads for copywriting tone reference).

**Open:**
- Confirmation UX: full form or guided wizard (step through meta > strategy > media > outcome)? Wizard reduces cognitive load but takes more clicks.
- Retrieval ranking: when multiple campaigns match, how to rank? By recency? By outcome rating? By budget similarity? Currently: by top proposition similarity score. May evolve.
- Sparse vector weight: 0.2 keyword / 0.8 semantic is a starting point. May need tuning after first 10 records are indexed and tested.
- Rerank cost: cross-encoder rerank adds ~200ms latency. Only justified for Media Planning profile where precision directly impacts plan quality. Other profiles skip it.

---

## Phase 6: Media Planning Intelligence

Upgrade the Resource Agent from a retrieval tool into a media planning system. Currently the pipeline skips three layers that experienced media planners perform: strategy interpretation, resource matrix design, and budget allocation by tier. Depends on Phase 5 (Campaign Knowledge Base) for historical reference data.

### 6.1 Media Planning Agent (new agent)

Sits between Strategy P2 and Resource Agent. Transforms strategy output into a structured media plan.

- [x] Strategy interpretation: convert strategy language into media requirements (e.g. "tech + emotional resonance + Gen-Z" becomes "relatable creator style, life-integrated tech narrative, audience-matching voice")
- [x] Resource matrix design: define tier structure (top-tier for awareness, mid-tier for amplification, KOC for UGC, media for credibility) with quantity and role per tier
- [x] Per-tier budget allocation: split the media budget (from Strategy P2's `budget_allocation`) across tiers with rationale
- [x] Output schema: `MediaPlan` (Pydantic) with `tiers[]`, each tier containing `role`, `count`, `budget_percentage`, `selection_criteria`, `platform_rationale`
- [x] HITL checkpoint: user confirms/edits matrix before Resource Agent executes retrieval
- [x] RAG context: retrieves top 3 similar CampaignRecords from Phase 5 knowledge base, includes their media_plan and outcome sections in prompt

Implementation: `backend/core/agents/media_planner.py`, `backend/core/models/media_plan.py`
Pipeline: `hitl_strategy → media_planner → hitl_media → resource_agent`
Frontend: `HitlMedia.tsx` (editable table with count + budget % adjustment)

**Knowledge sources for matrix design:**

| Source | What it provides | Implementation |
|--------|-----------------|----------------|
| Historical campaign records (Phase 5) | "We ran a similar campaign before, here is how it was structured and what worked" | ✅ Retrieved from `campaign_records` via metadata filter + semantic similarity. Returns structured media_plan + outcome data. |
| Current campaign context | Budget, objectives, timeline constraints | ✅ From Strategy P2 output (big_idea, channels, budget_allocation, kpis) |
| Industry tier frameworks | Default tier ratios and role definitions per campaign type | ⬜ Not in v1. Minimal principles hardcoded in system prompt as placeholder. Full Methodology Library deferred to Phase 5.9. |
| Distilled cross-campaign insights | "Across 10 beauty campaigns, KOC tier consistently delivers highest ROI" | ⬜ Not in v1. Requires `media_insights` collection + distillation batch job. See Phase 5.9. |

### 6.2 Resource Data Model Enhancement

Tiered retrieval requires richer resource profiles.

- [x] `tier` field: explicit tier label per resource (top/mid/tail/koc). Definitions vary by platform; cannot rely solely on follower count.
- [x] `content_style` restructured into dimensions:
  - `production_level`: high / medium / low (distinguishes polished from raw/authentic)
  - `persona_type`: expert / relatable / aspirational / entertaining
  - `voice_style`: educational / conversational / emotional / humorous
- [x] `audience_demographics`: structured object (age_range, gender_skew, city_tier, interest_tags) replacing flat `audience_tags` list
- [x] Decide: which new dimensions become metadata filters (discrete, exact match) vs remain in embedding text (semantic, fuzzy match)
  - Decision: `tier` → Pinecone metadata filter (discrete). `content_style_v2` dimensions + `audience_demographics` → embedding text (semantic matching).
- [x] Migration path for existing resources: `scripts/backfill_resource_profiles.py` — LLM batch inference of tier/content_style_v2/audience_demographics from existing freeform fields, updates MongoDB + refreshes Pinecone embeddings. Supports --dry-run, --client-id, --batch-size.

Implementation: `backend/core/models/resource.py` (ResourceTier, ContentStyle, AudienceDemographics)
Excel import: new CN aliases (层级, 制作水平, 人设类型, 表达风格, 年龄段, 性别倾向, 城市级别, 兴趣标签)
Embedding: `_resource_to_text()` updated to include structured fields

### 6.3 Tiered Retrieval Strategy

Resource Agent executes separate retrieval per tier with tier-appropriate parameters.

- [x] Per-tier query construction: uses `selection_criteria` from each MediaTier as semantic query (LLM writes tier-specific, queryable criteria)
- [x] Tier metadata filter: `tier` field used as Pinecone filter during per-tier retrieval
- [x] `_infer_resource_type()` maps tier label + channel to correct Pinecone namespace (kol/koc/media)
- [x] Fallback: when no media_plan present, reverts to generic per-type retrieval (backward compatible)
- [ ] Top/Mid/KOC/Media tier-specific scoring weights (currently relies on selection_criteria specificity + tier filter)
- [ ] Results explicitly grouped by tier in agent output schema (currently LLM groups in response text)

### 6.4 Budget Integration

- [x] Strategy P2 outputs channel-level budget split (social 60%, PR 25%, event 15%)
- [x] Media Planning Agent further splits per-channel budget into tier allocations (`budget_percentage` + `_compute_absolute_budgets()`)
- [x] User override: HITL allows manual budget adjustment at tier level (count + budget %)
- [x] If user specifies budget split in brief, Brief Analyzer extracts it (`StructuredBrief.budget_split`); Strategy P2 sees it in prompt context and respects it

### Design Decisions

**Decided:**
- `content_style` dimensions: 3 dimensions (production_level, persona_type, voice_style). Kept as `ContentStyle` sub-model. Old freeform `content_style` field retained for backward compat.
- Metadata vs embedding: `tier` is discrete → Pinecone metadata filter. Style dimensions and audience demographics are semantic → included in embedding text for fuzzy matching.
- Budget boundary: Strategy P2 owns channel-level allocation. Media Planning Agent owns tier-level split within each channel. No duplication.
- Single embedding per resource: structured fields concatenated into one embedding text string. Avoids complexity of multi-vector-per-resource.

**Open:**
- Tier definitions: platform-specific thresholds (Xiaohongshu 100k+ = top, Bilibili 100k+ = mid). Currently manual `tier` label on each resource. May add auto-classification based on follower_count + platform rules.

---

## Phase 7: Multi-Channel Access & Conversational UI

Lower usage barrier through chat interfaces; PPT stays in web dashboard.

### 7.1 Chat Bot Integration

- [ ] Webhook adapter layer for Feishu / WeCom / Slack
- [ ] User @ bot in group → triggers pipeline subset
- [ ] Suitable outputs: strategy direction, resource recommendations, copywriting, talking points, social copy
- [ ] NOT suitable: PPT generation (stays in web dashboard)
- [ ] Results rendered as structured cards (not raw text dumps)

### 7.2 Client Communication as Input

- [ ] Users paste/forward client chat logs as brief supplement
- [ ] Feeds into brief_analyzer as unstructured context
- [ ] Extracts: client needs, KPI targets, brand preferences, tone expectations

### 7.3 UI Architecture

- [ ] **Web Dashboard**: full pipeline, PPT generation/preview/edit, version management, analytics
- [ ] **Chat Bot**: quick Q&A, strategy/copy/resource queries, card-based results
- [ ] Both share the same backend API — no logic duplication

---

## Open Questions

- [x] ~~Visual reference file processing depth~~ → Phase 2.4 Claude Vision pipeline
- [ ] Social media data acquisition compliance (varies by locale)
- [x] ~~Resource database cold-start strategy~~ → Phase 4 (Excel enrichment + archive pipeline + progressive accumulation)
- [x] ~~Resource Agent trigger boundary~~ → Strategy output determines resource types automatically
- [x] ~~Narrative Agent prompt design~~ → Implemented with page-referenced JSON output
- [x] ~~Client feedback rerun~~ → Auto-suggest via RERUN_SUGGESTIONS mapping, user confirms with checkbox
- [x] ~~Initial PPT template count~~ → 5 templates created (social, PR, integrated, brand_refresh, default)
- [ ] Chat bot: message length limits per platform (Feishu ~30KB, WeCom ~2048 chars)
- [ ] Chat bot: auth model (how to map bot user → system user/client context)

