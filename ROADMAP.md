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

## Phase 5: Campaign Knowledge Base

Upgrade archive pipeline from fragmented text chunks into a structured, multi-layered knowledge system. Every agent in the pipeline benefits from historical campaign data. This phase establishes the data foundation that Phase 6 (Media Planning Intelligence) depends on.

### Why this matters

Most RAG systems store raw text chunks and retrieve by semantic similarity. This returns "similar words" but not "decision logic from similar situations." A structured campaign knowledge base enables agents to reference how similar campaigns were planned, what resource allocation was used, and what worked.

### 5.1 Knowledge Architecture (three layers)

```
Layer 1: Raw text chunks (existing)
  brand_history namespace in Pinecone
  Used for: style reference, tone matching, copywriting context
  Status: already implemented in Phase 4

Layer 2: Structured campaign records (this phase)
  MongoDB campaign_records collection + embedded summary in Pinecone
  Used for: finding similar past campaigns, referencing specific decisions and outcomes
  Consumers: all pipeline agents (each reads different fields)

Layer 3: Distilled industry insights (future, Phase 5.5)
  MongoDB media_insights collection
  Used for: cross-campaign patterns, industry benchmarks
  Initially: hand-written in prompts. Auto-distillation when case volume justifies.
```

### 5.2 CampaignRecord Schema Design

Each archived project produces one structured record. Fields organized by consuming agent:

```
CampaignRecord:
  meta:                              ← used for retrieval matching
    campaign_type                      (launch / branding / conversion / event / crisis)
    industry                           (beauty, automotive, tech, F&B, fashion, ...)
    budget_tier                        (under_100k / 100k_500k / 500k_2m / 2m_5m / above_5m)
    target_audience_summary            (one-line description)
    duration_days                      (campaign length)
    channels_used[]                    (xiaohongshu, douyin, weibo, pr, event, ...)
    client_id                          (tenant isolation)

  strategy_decisions:                ← Strategy P2 references
    big_idea
    positioning
    communication_logic
    rejected_directions[]              (what was tried and didn't work)
    client_feedback_summary            (what the client said about the strategy)

  media_plan:                        ← Media Planning Agent references
    total_media_budget
    channel_budget_split{}             (channel -> amount or percentage)
    tier_breakdown[]:
      tier                             (top / mid / tail / koc / media)
      count
      budget_allocated
      role                             (awareness / amplification / ugc / credibility)
      platform
      selection_criteria               (why this tier got this allocation)
    rationale                          (overall media plan reasoning)

  execution:                         ← Resource Agent references
    resources_used[]:
      name
      type                             (kol / koc / media / vendor)
      tier
      platform
      cost
      deliverables                     (post count, content type)
    content_formats[]                  (video, carousel, article, live stream)

  deck_info:                         ← Deck Orchestrator references
    slide_count
    chapter_structure[]                (section titles in order)
    presentation_style                 (data-heavy, visual, storytelling)

  outcome:                           ← all agents reference
    kpi_results{}                      (metric -> actual value)
    best_performing_tier
    best_performing_channel
    underperforming_areas[]
    lessons_learned[]
    reusable_insights[]                (transferable takeaways)
    overall_rating                     (1-5 scale, set during human confirmation)

  metadata:
    created_at
    confirmed_by                       (user who reviewed and confirmed)
    confidence                         (high / partial / low, based on source data completeness)
    source_archive_id                  (link back to raw archive upload)
```

Most fields are optional. LLM extracts what it can. User confirms and fills gaps.

### 5.3 Extraction Pipeline (extends existing archive)

```
Current flow (unchanged):
  upload → parse → extract_archive() → ArchiveExtraction
    → _distribute_to_brand_history() (text chunks → Pinecone)
    → _distribute_to_resources() (collaboration_history updates)

New addition:
  extract_archive() → also produces CampaignRecord (new schema fields)
    → _distribute_to_campaign_records():
        1. Store full record in MongoDB campaign_records collection
        2. Embed summary text into brand_history namespace with structured metadata
           (campaign_type, industry, budget_tier as Pinecone metadata filters)
    → Mark status as "pending_confirmation"
```

**LLM extraction prompt design:**
- Single extraction call produces both ArchiveExtraction (existing) and CampaignRecord (new)
- Prompt includes schema definition with field descriptions
- LLM marks each section's confidence (high if numbers are explicit in report, low if inferred)
- Fields not found in source are left null, not hallucinated

### 5.4 Human Confirmation Step

Extracted CampaignRecord is not immediately available for retrieval. Requires user review.

- [ ] `GET /api/v1/campaigns/{id}/review`: returns extracted record for confirmation UI
- [ ] `PUT /api/v1/campaigns/{id}/confirm`: user submits corrections, sets overall_rating, confirms
- [ ] Status flow: `pending_confirmation` → `confirmed` (only confirmed records are retrievable)
- [ ] UI: form pre-filled with LLM extraction, user edits fields, adds missing data (especially budget numbers and outcome metrics that may not be in the report)
- [ ] Low-confidence fields highlighted in UI for user attention

### 5.5 Retrieval Design

**How agents find relevant campaigns:**

Step 1: Metadata filter (narrow candidates)
```
campaign_type = "launch"
industry = "beauty"
budget_tier = "500k_2m"
status = "confirmed"
```

Step 2: Semantic similarity on summary embedding
```
query: "Gen-Z skincare launch, social-first, authentic tone"
→ cosine similarity against campaign summary embeddings
→ top 3-5 matches
```

Step 3: Return full structured records to requesting agent. Agent reads only its relevant module.

**Per-agent retrieval patterns:**

| Agent | Retrieves | Uses fields |
|-------|-----------|-------------|
| Strategy P2 | Similar campaigns by type + industry | strategy_decisions, outcome.lessons_learned |
| Media Planning | Similar campaigns by type + budget_tier | media_plan (full), outcome.best_performing_tier |
| Resource Agent | Similar campaigns by channels + industry | execution.resources_used, outcome.best_performing_channel |
| Deck Orchestrator | Similar campaigns by type | deck_info.chapter_structure, deck_info.slide_count |

### 5.6 Distilled Insights (deferred, manual first)

When a client accumulates 10+ confirmed campaign records:
- [ ] Auto-trigger insight distillation (batch LLM call across records)
- [ ] Output: industry-level patterns (e.g. "beauty launch campaigns: KOC tier consistently outperforms mid-tier on ROI")
- [ ] Store in `media_insights` collection, tagged by industry + campaign_type
- [ ] Media Planning Agent prompt includes relevant distilled insights as background context

**Initial approach (before auto-distillation):**
- Industry frameworks written directly in Media Planning Agent's system prompt as few-shot references
- Updated manually as team accumulates experience
- Migrated to RAG-retrievable format once content volume justifies the infrastructure

### Design Decisions (to be discussed)

- Extraction reliability: single LLM call for full CampaignRecord, or split into multiple focused calls (meta + media_plan + outcome separately)? Single call is cheaper but may lose precision on numeric fields.
- Confirmation UX: full form or guided wizard (step through meta → strategy → media → outcome)? Wizard reduces cognitive load but takes more clicks.
- Retrieval ranking: when multiple campaigns match, how to rank? By recency? By outcome rating? By budget similarity? Likely a weighted combination.
- Cross-client learning: should distilled insights be per-client or shared across the org? Per-client is safer (data isolation) but org-level learns faster.
- Cold start: first campaign archived has no similar records. System should gracefully fall back to prompt-embedded industry knowledge without degrading output quality.

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

