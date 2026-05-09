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
- [x] Third-party social data APIs (locale-specific: Chanmama/Feigua for China, CreatorIQ for global)
- [x] Richer competitor reports: social_presence, content_trends, risks, recommended_approach
- [x] Locale-aware source selection (auto-detect CN vs global from brief content)
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
  - Strategy learnings → `brand_history_{client_id}` namespace
  - Industry insights → client knowledge base
  - Audience feedback/sentiment → audience insight pool
- [x] Built on existing file upload + RAG pipeline, extended with extraction + routing
- [x] `GET /api/v1/projects/{id}/archive` to check extraction status and results

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

---

## Phase 5: Media Planning Intelligence

Upgrade the Resource Agent from a retrieval tool into a media planning system. Currently the pipeline skips three layers that experienced media planners perform: strategy interpretation, resource matrix design, and budget allocation by tier.

### 5.1 Media Planning Agent (new agent)

Sits between Strategy P2 and Resource Agent. Transforms strategy output into a structured media plan.

- [ ] Strategy interpretation: convert strategy language into media requirements (e.g. "tech + emotional resonance + Gen-Z" becomes "relatable creator style, life-integrated tech narrative, audience-matching voice")
- [ ] Resource matrix design: define tier structure (top-tier for awareness, mid-tier for amplification, KOC for UGC, media for credibility) with quantity and role per tier
- [ ] Per-tier budget allocation: split the media budget (from Strategy P2's `budget_allocation`) across tiers with rationale
- [ ] Output schema: `MediaPlan` (Pydantic) with `tiers[]`, each tier containing `role`, `count`, `budget_share`, `selection_criteria`, `rationale`
- [ ] HITL checkpoint: user confirms/edits matrix before Resource Agent executes retrieval

**Knowledge sources for matrix design:**

| Source | What it provides | Implementation |
|--------|-----------------|----------------|
| Industry reference frameworks | Default tier ratios by campaign type (e.g. beauty launch: 30% top + 40% mid + 20% KOC + 10% media) | Prompt-embedded few-shot examples initially. Later: dedicated `industry_knowledge` Pinecone namespace maintained by admin. |
| Historical campaign RAG | "We ran a similar campaign before, here's how it was structured and what worked" | Requires structured archive storage (see 5.2). Retrieved from `brand_history` with campaign-level metadata filtering. |
| Current campaign context | Budget, objectives, timeline constraints | From Strategy P2 output (big_idea, channels, budget_allocation, kpis) |

### 5.2 Historical Campaign Structured Storage

Current archive pipeline stores text chunks. Media Planning needs structured, queryable campaign records.

- [ ] Design `campaign_record` schema: campaign type, total budget, tier breakdown, resource list per tier, performance metrics, key learnings
- [ ] Extend archive extraction to produce `campaign_record` in addition to current text chunks
- [ ] Store in MongoDB `campaign_records` collection (queryable by type, budget range, client)
- [ ] Embed campaign summary text into `brand_history` namespace with structured metadata (campaign_type, budget_range, outcome_rating)
- [ ] Retrieval: Media Planning Agent queries by campaign similarity (type + budget + objective), receives structured records as context

### 5.3 Resource Data Model Enhancement

Tiered retrieval requires richer resource profiles.

- [ ] `tier` field: explicit tier label per resource (top/mid/tail/koc). Definitions vary by platform; cannot rely solely on follower count.
- [ ] `content_style` restructured into dimensions:
  - `production_level`: high / medium / low (distinguishes polished from raw/authentic)
  - `persona_type`: expert / relatable / aspirational / entertaining
  - `voice_style`: educational / conversational / emotional / humorous
- [ ] `audience_demographics`: structured object (age_range, gender_skew, city_tier, interest_tags) replacing flat `audience_tags` list
- [ ] Decide: which new dimensions become metadata filters (discrete, exact match) vs remain in embedding text (semantic, fuzzy match)
- [ ] Migration path for existing resources: backfill strategy for new structured fields from existing freeform data

### 5.4 Tiered Retrieval Strategy

Resource Agent executes separate retrieval per tier with tier-appropriate parameters.

- [ ] Per-tier query construction: different weight on followers_count, content_style dimensions, audience match
- [ ] Top-tier: high followers + high relevance + verified recently
- [ ] Mid-tier: moderate followers + high category match + good past performance
- [ ] KOC: low followers + high authenticity (production_level=low) + audience demographic match
- [ ] Media: beat match + outlet credibility + publish frequency
- [ ] Results grouped by tier in output, matching the matrix structure from Media Planning Agent

### 5.5 Budget Integration

- [ ] Strategy P2 outputs channel-level budget split (social 60%, PR 25%, event 15%)
- [ ] Media Planning Agent further splits per-channel budget into tier allocations
- [ ] User override: HITL allows manual budget adjustment at both levels
- [ ] If user specifies budget split in brief, Brief Analyzer extracts it; Strategy P2 respects it

### Design Decisions (to be discussed)

- Industry knowledge: prompt-embedded few-shot vs dedicated RAG namespace? Start with prompt, migrate to RAG when content volume justifies.
- Historical data cold-start: first few campaigns have no history. Fallback to industry frameworks only. System improves after 5-10 archived campaigns per client.
- `content_style` dimensions: how many are enough without creating data entry burden? Current thinking: 3 dimensions (production_level, persona_type, voice_style) cover 80% of media planning decisions.
- Tier definitions: platform-specific thresholds (Xiaohongshu 100k+ = top, Bilibili 100k+ = mid). Store as configurable rules or let LLM infer from follower_count + engagement_rate?
- Embedding architecture: when content_style becomes multi-dimensional, do we keep one embedding per resource or create multiple embeddings per resource (one per dimension)?

---

## Phase 6: Multi-Channel Access & Conversational UI

Lower usage barrier through chat interfaces; PPT stays in web dashboard.

### 6.1 Chat Bot Integration

- [ ] Webhook adapter layer for Feishu / WeCom / Slack
- [ ] User @ bot in group → triggers pipeline subset
- [ ] Suitable outputs: strategy direction, resource recommendations, copywriting, talking points, social copy
- [ ] NOT suitable: PPT generation (stays in web dashboard)
- [ ] Results rendered as structured cards (not raw text dumps)

### 6.2 Client Communication as Input

- [ ] Users paste/forward client chat logs as brief supplement
- [ ] Feeds into brief_analyzer as unstructured context
- [ ] Extracts: client needs, KPI targets, brand preferences, tone expectations

### 6.3 UI Architecture

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

