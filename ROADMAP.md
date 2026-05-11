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
  - Strategy learnings → `brand_history_{client_id}` namespace (to be replaced by CampaignRecord in Phase 5)
  - Industry insights → client knowledge base
  - Audience feedback/sentiment → audience insight pool
- [x] Built on existing file upload + RAG pipeline, extended with extraction + routing
- [x] `GET /api/v1/projects/{id}/archive` to check extraction status and results

> **Phase 5 migration note:** Campaign Knowledge Base extraction now runs in parallel with existing archive pipeline. Both `_distribute_to_brand_style()` and `extract_campaign_record()` execute on every archive upload — the former writes strategy text to brand_style namespace (still queried by agents), the latter stores structured CampaignRecord in MongoDB (pending human confirmation + proposition indexing in 5.5). Once 5.5 is complete and agents retrieve from campaign_knowledge namespace, `_distribute_to_brand_style()` will be removed and brand_style namespace narrowed to copywriting style/tone reference only.

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
Brand Library                Constraint        Pinecone vectors            Implemented
Campaign Knowledge Base      Reference         MongoDB + Pinecone props    This phase
Methodology Library          Guidance          Agent system prompts        Implemented (static)
Industry Knowledge           Context           Real-time search + cache    Implemented
Resource Library             Execution pool    MongoDB + Pinecone vectors  Implemented
```

Three layers have dedicated storage (Brand Library, Campaign Knowledge Base, Resource Library). Methodology lives in agent prompts and evolves via auto-distillation from Campaign Knowledge Base once enough records accumulate (Phase 5.9). Industry Knowledge is served by Research Agent's real-time search with 30-day semantic caching.

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
  Storage: MongoDB campaign_records + Pinecone campaign_knowledge_{client_id}
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

**Methodology Library evolution path:**

```
Now:     tier allocation frameworks, planning heuristics written in agent system prompts
Phase 5.9: auto-distill patterns from 10+ confirmed CampaignRecords
           (e.g. "beauty launches: KOC consistently outperforms mid-tier on ROI")
Future:  if methodology content grows beyond prompt capacity, migrate to RAG-retrievable format
```

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
    client_id                          (tenant isolation)

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

  outcome:                           ← all agents reference ("what happened")
    kpi_results{}                      (metric -> actual value)
    best_performing_tier
    best_performing_channel
    underperforming_areas[]
    lessons_learned[]                  (project-specific takeaways)
    reusable_insights[]                (transferable patterns for other projects)
    overall_rating                     (1-5 scale, set during human confirmation)

  metadata:
    status                             (pending_confirmation / confirmed)
    confidence                         (high / partial / low, based on source data completeness)
    source_archive_id                  (link back to raw archive upload)
    created_at
    confirmed_by                       (user who reviewed and confirmed)
    confirmed_at
```

**Communication vs Media distinction:**
- Communication plan = strategic ("怎么打"): channel roles, content direction, phasing, cross-platform interaction
- Media plan = tactical ("买什么花多少"): budget allocation, tier breakdown, only paid/purchased resources
- Example: offline event as a communication touchpoint (brand event in launch phase) → communication_plan. Offline event as a purchased venue/media slot → media_plan.

All fields are optional. LLM extracts what it can. User confirms and fills gaps.

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

Note: `_distribute_to_brand_style()` currently still writes strategy learnings to brand_style namespace — this is intentional during transition. CampaignRecord extraction runs in parallel but records are not yet retrievable by agents (pending 5.5 proposition indexing). Once proposition vectors are live and agents query campaign_knowledge namespace instead, `_distribute_to_brand_style()` will be removed and `extract_archive()` narrowed to resource performance extraction only.

**Three parallel LLM extraction calls** (split by information distribution in reports):

```
Call 1: ExtractionBackground (meta + strategy_decisions + communication_plan + deck_info)
  → Report sections: project background, strategy rationale, planning chapters
  → System prompt focuses on "what direction was chosen and why" + "how to fight"

Call 2: ExtractionExecution (media_plan + execution)
  → Report sections: budget tables, resource lists, execution summaries
  → System prompt focuses on "what to buy" + "how it was done"

Call 3: ExtractionOutcome (outcome + client_learnings)
  → Report sections: results, post-campaign analysis, team retrospective, client feedback
  → System prompt focuses on "what happened" + "what to learn" + "how this client decides"

Merge: results combined, confidence = min(call1, call2, call3)
Partial failure: if one call fails, others still contribute (graceful degradation)
```

**Why 3 calls instead of 1:**
- Information distribution: recap reports scatter strategy in early pages, execution in mid-section, results at the end. A single call must attend to all sections simultaneously.
- Schema complexity: CampaignRecord has 50+ fields across 5 dimensions. Single-call structured output degrades in quality past ~30 fields.
- Prompt specialization: each call gets domain-specific extraction guidance (strategy analyst, media planner, evaluation expert).
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

- [ ] `GET /api/v1/campaigns/{id}/review`: returns extracted record for confirmation UI
- [ ] `PUT /api/v1/campaigns/{id}/confirm`: user submits corrections, sets overall_rating, confirms
- [ ] Status flow: `pending_confirmation` → `confirmed` (only confirmed records are retrievable)
- [ ] UI: form pre-filled with LLM extraction, user edits fields, adds missing data (especially budget numbers and outcome metrics that may not be in the report)
- [ ] Low-confidence fields highlighted in UI for user attention

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

- [ ] LLM-based proposition extraction from confirmed CampaignRecord (gpt-4o-mini or equivalent, low cost per record)
- [ ] Each proposition stored in MongoDB `campaign_propositions` collection with campaign_record_id back-reference
- [ ] Each proposition embedded with meta prefix (contextual embedding) and upserted to `campaign_knowledge_{client_id}` Pinecone namespace
- [ ] Metadata on each vector: campaign_record_id, module, campaign_type, industry, budget_tier
- [ ] Fallback: if proposition extraction fails, embed full module text with meta prefix

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
- [ ] Media Planning profile uses cross-encoder rerank (heavier but highest precision needed)
- [ ] Media Planning agent integrated (blocked on Phase 6 Media Planning Agent)
- [ ] Rerank implementation for media_planning profile

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

Prevent agents from blindly using irrelevant historical data.

- [ ] After retrieval, LLM judges: "Are these historical campaigns similar enough to inform the current plan?" (sufficient / partial / insufficient)
- [ ] If sufficient: agent uses full retrieved context
- [ ] If partial: agent uses retrieved context but adds explicit caveat ("limited historical data for this scenario, falling back to industry frameworks")
- [ ] If insufficient: agent falls back entirely to prompt-embedded industry knowledge. No historical references cited.
- [ ] Prevents: "We did a beauty launch before so here's the plan" when the retrieved campaign was actually a beauty branding campaign with completely different objectives

### 5.9 Distilled Insights (Methodology Library auto-evolution)

This phase connects Campaign Knowledge Base back to the Methodology Library. When enough project records accumulate, the system auto-distills patterns and updates agent prompts.

When a client accumulates 10+ confirmed campaign records:
- [ ] Auto-trigger insight distillation (batch LLM call across records)
- [ ] Output: industry-level patterns (e.g. "beauty launch campaigns: KOC tier consistently outperforms mid-tier on ROI")
- [ ] Store in `media_insights` collection, tagged by industry + campaign_type
- [ ] Media Planning Agent prompt includes relevant distilled insights as background context
- [ ] Closes the loop: Campaign Knowledge Base (raw experience) feeds Methodology Library (distilled guidance)

**Initial approach (before auto-distillation):**
- Industry frameworks written directly in Media Planning Agent's system prompt as few-shot references (this IS the Methodology Library today)
- Updated manually as team accumulates experience
- Migrated to RAG-retrievable format once content volume justifies the infrastructure

### Design Decisions

**Decided:**
- Cross-client retrieval: org-wide by default. Records belong to client_id (ownership) but retrieval matches across all clients by industry + campaign_type + budget_tier. Agent responses are desensitized (no client_name). Admin can mark records "client_only" for competing brand isolation.
- Knowledge boundary: Brand Library stores brand identity (constraints, style). Campaign Knowledge Base stores project experience (decisions, outcomes). Boundary rule: if value survives rewording, it is Campaign Knowledge Base. If value IS the wording, it is Brand Library.

**Open:**
- Extraction reliability: single LLM call for full CampaignRecord, or split into multiple focused calls (meta + media_plan + outcome separately)? Single call is cheaper but may lose precision on numeric fields.
- Confirmation UX: full form or guided wizard (step through meta > strategy > media > outcome)? Wizard reduces cognitive load but takes more clicks.
- Retrieval ranking: when multiple campaigns match, how to rank? By recency? By outcome rating? By budget similarity? Likely a weighted combination.
- Cold start: first campaign archived has no similar records. System should gracefully fall back to prompt-embedded industry knowledge without degrading output quality.
- Proposition granularity: how many propositions per campaign record? Too few loses detail, too many increases retrieval noise. Estimate: 8-15 per record depending on data completeness.
- Sparse vector weight: 0.2 keyword / 0.8 semantic is a starting point. May need tuning after first 10 records are indexed and tested.
- Rerank cost: cross-encoder rerank adds ~200ms latency. Only justified for Media Planning profile where precision directly impacts plan quality. Other profiles skip it.

---

## Phase 6: Media Planning Intelligence

Upgrade the Resource Agent from a retrieval tool into a media planning system. Currently the pipeline skips three layers that experienced media planners perform: strategy interpretation, resource matrix design, and budget allocation by tier. Depends on Phase 5 (Campaign Knowledge Base) for historical reference data.

### 6.1 Media Planning Agent (new agent)

Sits between Strategy P2 and Resource Agent. Transforms strategy output into a structured media plan.

- [ ] Strategy interpretation: convert strategy language into media requirements (e.g. "tech + emotional resonance + Gen-Z" becomes "relatable creator style, life-integrated tech narrative, audience-matching voice")
- [ ] Resource matrix design: define tier structure (top-tier for awareness, mid-tier for amplification, KOC for UGC, media for credibility) with quantity and role per tier
- [ ] Per-tier budget allocation: split the media budget (from Strategy P2's `budget_allocation`) across tiers with rationale
- [ ] Output schema: `MediaPlan` (Pydantic) with `tiers[]`, each tier containing `role`, `count`, `budget_share`, `selection_criteria`, `rationale`
- [ ] HITL checkpoint: user confirms/edits matrix before Resource Agent executes retrieval
- [ ] RAG context: retrieves top 3 similar CampaignRecords from Phase 5 knowledge base, includes their media_plan and outcome sections in prompt

**Knowledge sources for matrix design:**

| Source | What it provides | Implementation |
|--------|-----------------|----------------|
| Industry reference frameworks | Default tier ratios by campaign type (e.g. beauty launch: 30% top + 40% mid + 20% KOC + 10% media) | Prompt-embedded few-shot examples initially. Later: dedicated `industry_knowledge` Pinecone namespace maintained by admin. |
| Historical campaign records (Phase 5) | "We ran a similar campaign before, here is how it was structured and what worked" | Retrieved from `campaign_records` via metadata filter + semantic similarity. Returns structured media_plan + outcome data. |
| Distilled insights (Phase 5.6) | "Across 10 beauty campaigns, KOC tier consistently delivers highest ROI" | From `media_insights` collection, matched by industry + campaign_type. |
| Current campaign context | Budget, objectives, timeline constraints | From Strategy P2 output (big_idea, channels, budget_allocation, kpis) |

### 6.2 Resource Data Model Enhancement

Tiered retrieval requires richer resource profiles.

- [ ] `tier` field: explicit tier label per resource (top/mid/tail/koc). Definitions vary by platform; cannot rely solely on follower count.
- [ ] `content_style` restructured into dimensions:
  - `production_level`: high / medium / low (distinguishes polished from raw/authentic)
  - `persona_type`: expert / relatable / aspirational / entertaining
  - `voice_style`: educational / conversational / emotional / humorous
- [ ] `audience_demographics`: structured object (age_range, gender_skew, city_tier, interest_tags) replacing flat `audience_tags` list
- [ ] Decide: which new dimensions become metadata filters (discrete, exact match) vs remain in embedding text (semantic, fuzzy match)
- [ ] Migration path for existing resources: backfill strategy for new structured fields from existing freeform data

### 6.3 Tiered Retrieval Strategy

Resource Agent executes separate retrieval per tier with tier-appropriate parameters.

- [ ] Per-tier query construction: different weight on followers_count, content_style dimensions, audience match
- [ ] Top-tier: high followers + high relevance + verified recently
- [ ] Mid-tier: moderate followers + high category match + good past performance
- [ ] KOC: low followers + high authenticity (production_level=low) + audience demographic match
- [ ] Media: beat match + outlet credibility + publish frequency
- [ ] Results grouped by tier in output, matching the matrix structure from Media Planning Agent

### 6.4 Budget Integration

- [ ] Strategy P2 outputs channel-level budget split (social 60%, PR 25%, event 15%)
- [ ] Media Planning Agent further splits per-channel budget into tier allocations
- [ ] User override: HITL allows manual budget adjustment at both levels
- [ ] If user specifies budget split in brief, Brief Analyzer extracts it; Strategy P2 respects it

### Design Decisions (to be discussed)

- `content_style` dimensions: how many are enough without creating data entry burden? Current thinking: 3 dimensions (production_level, persona_type, voice_style) cover 80% of media planning decisions.
- Tier definitions: platform-specific thresholds (Xiaohongshu 100k+ = top, Bilibili 100k+ = mid). Store as configurable rules or let LLM infer from follower_count + engagement_rate?
- Embedding architecture: when content_style becomes multi-dimensional, do we keep one embedding per resource or create multiple embeddings per resource (one per dimension)?

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

