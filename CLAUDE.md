# Pitchcraft — Claude Code Guide

This file is the primary reference for Claude Code sessions working on this codebase.

---

## Project Overview

Pitchcraft is an AI-powered proposal automation platform for PR/marketing agencies. It converts a client brief into a presentation-ready PowerPoint deck using a LangGraph pipeline (8 LLM agents, 5 in-graph HITL checkpoints) with request-per-pause HTTP resume.

**Stack:**
- Backend: FastAPI + LangGraph (`AsyncRedisSaver` checkpoint) + Celery (async jobs only) + MongoDB + Pinecone
- Frontend: Next.js 14 (App Router) + Redux Toolkit + Tailwind CSS
- Infrastructure: Docker Compose (8 services), Terraform (AWS ECS Fargate)
- AI: Anthropic Claude via `langchain_anthropic`, embeddings via sentence-transformers

---

## Development Workflow

### There is NO hot-reload. Always rebuild after changing code.

```bash
# After any backend (Python) change:
make build s=backend && make up

# After any frontend (Next.js) change:
make build s=frontend && make up

# After any worker (Celery) change:
make build s=worker && make up

# Rebuild multiple services at once:
make build s=backend && make build s=worker && make up
```

**`make restart s=<service>`** only restarts the process inside the existing container — it does NOT pick up source code changes.

### Other useful commands

```bash
make up                  # Start all services (detached)
make down                # Stop all services
make ps                  # Show container status and health
make logs                # Tail all logs
make logs s=backend      # Tail a single service log
make logs s=worker       # Tail Celery worker log (async task progress)
```

### Viewing async task logs

Celery tasks (e.g., archive processing, proposition indexing) run in the `worker` container. To see processing progress:

```bash
make logs s=worker
```

**Proposal pipeline** runs in the `backend` container via FastAPI `BackgroundTasks` — not Celery. Tail pipeline progress with:

```bash
make logs s=backend
```

---

## Auth & API Calls

### JWT tokens expire after 7 days

Tokens are stored in `localStorage["token"]`. Refresh tokens are stored in `localStorage["refresh_token"]`. The expiry is set via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080` in `.env`.

### Always use `apiFetch`, never raw `fetch`

Every authenticated API call **must** use the `apiFetch` helper from `frontend/lib/api.ts`:

```typescript
import { apiFetch } from "@/lib/api";

const res = await apiFetch("/api/v1/some-endpoint", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});
```

`apiFetch` automatically:
1. Adds `Authorization: Bearer <token>` header
2. On 401: tries to refresh the token using `refresh_token`
3. On refresh failure: clears storage and redirects to `/login`

**For multipart/FormData uploads, do NOT set `Content-Type`** — the browser sets it with the boundary:

```typescript
const form = new FormData();
form.append("file", file);
form.append("client_id", clientId);
const res = await apiFetch("/api/v1/campaigns/upload", { method: "POST", body: form });
// No Content-Type header — browser fills it in automatically
```

---

## Frontend Pages

All pages live in `frontend/app/` and use the Next.js App Router.

| Route | File | Purpose |
|-------|------|---------|
| `/login` | `app/login/page.tsx` | Register / login |
| `/pipeline` | `app/pipeline/page.tsx` | Run a new proposal pipeline; 5 in-graph HITL checkpoints |
| `/proposals/[id]` | `app/proposals/[id]/page.tsx` | Proposal detail, feedback, version history |
| `/clients` | `app/clients/page.tsx` | List/create clients; links to client detail |
| `/clients/[clientId]` | `app/clients/[clientId]/page.tsx` | Client detail: projects, brand profile, resource library |
| `/projects/[projectId]` | `app/projects/[projectId]/page.tsx` | Project detail: overview/edit, proposals tab, archive upload |
| `/files` | `app/files/page.tsx` | File library (upload, visual ref thumbnails) |
| `/resources` | `app/resources/page.tsx` | Resource library (list, filter, Excel import) |
| `/campaigns` | `app/campaigns/page.tsx` | **Campaign KB main page**: upload recap docs, review pending records |
| `/campaigns/[recordId]` | `app/campaigns/[recordId]/page.tsx` | Review/edit/confirm individual campaign records |
| `/research` | `app/research/page.tsx` | Research data display + manual refresh |
| `/analytics` | `app/analytics/page.tsx` | Analytics dashboard (KPIs, stage performance, feedback stats) |

### Navigation

Sidebar: `frontend/components/layout/Sidebar.tsx`
- "Clients & Projects" → `/clients`
- "Campaign KB" → `/campaigns`

---

## Campaign Knowledge Base — Full Flow

The Campaign KB is how the agency accumulates institutional memory from past projects.

### 1. Upload a recap document

**Entry point:** `/campaigns` page → Upload panel

1. User selects a client from the dropdown (or creates one inline)
2. User picks a `.pdf`, `.docx`, `.pptx`, or `.ppt` file (max 30 MB)
3. Frontend POSTs to `POST /api/v1/campaigns/upload` (multipart: `client_id` + `file`)
4. Backend saves the file, inserts a `project_archives` record, and fires a Celery task

### 2. Async extraction (Celery worker)

`backend/core/rag/archive_process.py` → `process_archive_task`

1. Parses the file (PDF, PPTX, DOCX) into plain text
2. Calls `extract_campaign_record()` (3 parallel LLM calls):
   - **Background call**: meta + strategy + communication plan (first 40k chars)
   - **Execution call**: media plan + execution details (first 40k chars)
   - **Outcome call**: KPIs + lessons (last 20k chars) — skipped for proposals
3. Saves a `CampaignRecord` (status: `pending_confirmation`) to `campaign_records`
4. Auto-detects language (Chinese vs English) and uses the appropriate prompt

### 3. Human review

`/campaigns` page auto-polls every 5 seconds after upload (up to 3 minutes) and switches to the Pending tab when a new record appears.

Clicking a record opens `/campaigns/[recordId]` for full review and editing:
- All extracted fields are editable inline
- Campaign Type uses enum: `product_launch / brand_campaign / performance / event_activation / big_sale_promo / influencer_kol / crisis_comms / always_on / other`
- Array fields (channels, content themes, etc.) display in textarea — one JSON array

### 4. Confirm → vector indexing

Clicking **Confirm** calls `PUT /api/v1/campaigns/{id}/confirm` with optional field edits.

Backend then (in background):
1. Sets status to `confirmed`
2. Calls `index_campaign_propositions()` → extracts atomic propositions from the record
3. Embeds each proposition and upserts to Pinecone namespace `campaign_knowledge_{org_id}`
4. Vector IDs: `camp_{record_id}_{proposition_index}`
5. Stores proposition docs in `campaign_propositions` MongoDB collection

### 5. Pipeline agents retrieve from Campaign KB

All 8 agents call `retrieve_campaign_context(query, org_id, top_k, filters)` which searches Pinecone and returns relevant historical propositions.

### 6. Deleting records

- **Pending records**: DELETE removes only the MongoDB `campaign_records` doc
- **Confirmed records**: DELETE removes MongoDB doc + background task purges `campaign_propositions` + Pinecone vectors

The delete button is always visible on the record detail page (`/campaigns/[recordId]`). Confirmed record deletion shows a warning dialog before proceeding.

---

## Proposal Pipeline — Full Flow

The proposal pipeline is a LangGraph `StateGraph` with `interrupt()` on 5 HITL nodes. Execution is **stateless per HTTP request** — no long-lived coroutine, no Redis pub/sub for resume.

### State layers (do not confuse them)

| Layer | Storage | Purpose |
|-------|---------|---------|
| LangGraph checkpoint | `AsyncRedisSaver`, `thread_id=pipeline_id` | Graph execution state across `start` / `resume_pipeline` calls; survives process restarts |
| App state snapshot | Redis `pipeline:{id}:state` | Human-readable dict for frontend GET endpoints; updated after each non-HITL node |
| Status | Redis `pipeline:{id}:status` | `{status, current_node}` for polling |
| Node timings | Redis `pipeline:{id}:timings` | Accumulated per-node metrics across execution segments |

`RequestBudget` is excluded from Redis JSON — recreated fresh on each `start()` / `resume_pipeline()` call.

### HITL design highlights

- **Checkpoint vs app state**: LangGraph checkpoint (`AsyncRedisSaver`) is opaque and managed by LangGraph for resume. `pipeline:{id}:state` is the denormalized snapshot for frontend GET — never use one as a substitute for the other.
- **Confirm flow** (`pipeline.py`): validate paused + matching `node` → `set_status("running")` → `BackgroundTasks.add_task(resume_pipeline)` — optimistic lock before async work starts.
- **Rerun priming**: `get_rerun_predecessors(state, rerun_from)` + `_RERUN_PREDECESSORS` — fan-in nodes need multiple `aupdate_state(as_node=...)` calls; `deck_orchestrator` uses `hitl_media` or `resource_agent` based on whether Resource Agent ran.
- **Per-node Redis writes**: non-HITL nodes call `save_state()` after each step in `_stream_run` for crash recovery and live GET data, not only at interrupts.

### 1. Start pipeline

**Entry point:** `/pipeline` page → Brief Input

1. Frontend POSTs to `POST /api/v1/pipeline/start` with `client_id`, `raw_brief`, `output_language`
2. Backend returns `{pipeline_id, status: "started"}` (202)
3. `BackgroundTasks` calls `executor.start(initial_state)` — runs until first `interrupt()` or completion, then **returns**

### 2. Real-time progress (WebSocket, receive-only)

Frontend opens `ws://.../ws/pipeline/{pipeline_id}` via `usePipelineSocket`.

Server pushes: `node_entered`, `hitl_required`, `slide_generated`, `pipeline_complete`.

**HITL responses are NOT sent over WebSocket.** Clients may send messages but the server ignores them.

### 3. HITL confirm / revise / rerun (HTTP)

When status is `paused`, frontend calls `POST /api/v1/pipeline/{id}/confirm` via `api.confirmNode()`:

```typescript
await api.confirmNode(pipelineId, {
  node: "hitl_brief",       // must match current paused node
  action: "confirm",        // "confirm" | "revise" | "rerun"
  edits: { ... },           // optional field edits
  feedback: "...",          // for revise
  refresh_research: true,   // optional
  rerun_from: "research_agent",  // for action="rerun" at hitl_strategy
  flagged_indices: [2, 5],  // for hitl_gallery
});
```

Backend starts `executor.resume_pipeline(response)` as a short-lived background task → `Command(resume=response)` → runs until next interrupt or completion.

**5 in-graph HITL nodes:** `hitl_brief` → `hitl_strategy` → `hitl_media` → `hitl_structure` → `hitl_gallery`

Post-pipeline client feedback on `/proposals/[id]` can trigger rerun — separate from in-graph HITL.

### 4. Graph topology highlights

- Fan-out: `hitl_brief` → `research_agent` ∥ `strategy_phase1` → fan-in at `strategy_phase2`
- Conditional: `hitl_media` → `resource_agent` or skip to `deck_orchestrator` when `resource_types_needed=[]`
- Serial: `slide_content` → `narrative_agent` → `hitl_gallery` (not parallel)

### 5. Rerun

**External rerun** (`POST /api/v1/pipeline/{id}/rerun` or proposal feedback):
- `executor.start(redis_state, start_from=node)` loads app state, primes checkpointer via `aupdate_state(as_node=predecessor)`, streams from node

**Inline rerun** (HITL Strategy `action="rerun"`):
- Handled within a single `resume_pipeline()` call — `_stream_run` detects `rerun_from` in node output, primes checkpointer, restreams

`RERUN_SUGGESTIONS` in `backend/core/models/feedback.py` maps feedback targets to nodes (`strategy_phase2`, `deck_orchestrator`, `slide_content`, `resource_agent`).

### 6. Key executor methods

| Method | When | Returns |
|--------|------|---------|
| `start(initial_state)` | `POST /start` | Exits at first HITL interrupt or completion |
| `resume_pipeline(response)` | `POST /confirm` | Exits at next interrupt or completion |
| `start(state, start_from=node)` | `POST /rerun`, feedback rerun | Same as start with primed checkpoint |

---

## Backend Endpoints

### Key pipeline endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/pipeline/start` | Start pipeline → background `executor.start()` |
| `POST` | `/api/v1/pipeline/{id}/confirm` | HITL response → background `executor.resume_pipeline()` |
| `POST` | `/api/v1/pipeline/{id}/rerun` | Rerun from node → background `executor.start(state, start_from)` |
| `POST` | `/api/v1/pipeline/{id}/recover` | Recover stalled pipeline (process restart); reads LangGraph checkpoint to restore `paused` or `error` |
| `GET` | `/api/v1/pipeline/{id}/status` | Current status + confirmation flags; auto-recovers if `running` > 5 min |
| `GET` | `/api/v1/pipeline/{id}/brief` | Structured brief for HITL 1 |
| `GET` | `/api/v1/pipeline/{id}/strategy` | Strategy + research for HITL 2 |
| `GET` | `/api/v1/pipeline/{id}/media-plan` | Media plan for HITL 3 |
| `GET` | `/api/v1/pipeline/{id}/slides` | Slides + narrative for HITL 5 |

### Key campaign endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/campaigns` | List all records (filter by client_id, status) |
| `GET` | `/api/v1/campaigns/pending` | List pending records |
| `GET` | `/api/v1/campaigns/search` | Search confirmed records by metadata |
| `POST` | `/api/v1/campaigns/upload` | Upload a recap document → triggers async extraction |
| `GET` | `/api/v1/campaigns/{id}` | Get a single record |
| `PUT` | `/api/v1/campaigns/{id}/confirm` | Confirm + optionally edit a record → triggers indexing |
| `DELETE` | `/api/v1/campaigns/{id}` | Delete record (+ Pinecone cleanup for confirmed records) |

### Route ordering matters in FastAPI

Sub-paths like `/pending`, `/search`, `/upload` **must be defined before** `/{record_id}` in the router, otherwise FastAPI matches `"pending"` as a record ID. See `backend/api/v1/endpoints/campaigns.py`.

---

## MongoDB Collections

| Collection | Contents |
|------------|---------|
| `users` | User accounts, org membership, roles |
| `organizations` | Org settings |
| `clients` | Client/brand profiles |
| `projects` | Projects under clients |
| `proposals` | Pipeline outputs (versioned) |
| `project_archives` | Uploaded documents (metadata + storage path) |
| `campaign_records` | Extracted CampaignRecord documents (pending + confirmed) |
| `campaign_propositions` | Atomic propositions extracted from confirmed records |
| `resources` | Resource library items (KOLs, media, vendors) |
| `files` | Uploaded brand/reference files |
| `feedback` | User feedback on proposals |

---

## Data Models

### CampaignRecord (5 dimensions)

```
CampaignRecord
├── meta              CampaignMeta          — campaign_type, industry, budget_tier, client_name, ...
├── strategy_decisions StrategyDecisions    — big_idea, positioning, rejected_directions, ...
├── communication_plan CommunicationPlan    — channel_mix, phasing_structure, content_themes, ...
├── media_plan        MediaPlan             — total_budget, tier_breakdown, channel_budget_split
├── execution         ExecutionDetail       — resources_used, activities, actual_timeline
├── outcome           Outcome               — kpi_results, lessons_learned, reusable_insights
├── client_learnings  ClientLearnings       — decision_style, kpi_priorities (manual entry)
└── deck_info         DeckInfo              — slide_count, chapter_structure
```

`record_type`: `"proposal"` (pitch deck) or `"campaign"` (recap with results)
`status`: `"pending_confirmation"` → `"confirmed"`

---

### Resource (KOL / Media / Vendor / Placement)

A Resource is a **person or entity**, not a platform account. Multi-platform KOLs are one record with a `platforms` list.

```
Resource
├── org_id: str                              — always set from JWT; used for shared pool isolation
├── client_id: str                           — empty for shared resources
├── scope: "shared" | "client"              — "shared" = agency-wide pool; "client" = client-specific
├── name, type, tier, tags, pricing, status
├── platforms: list[PlatformEntry]           — one entry per platform
│    └── PlatformEntry: name, followers_raw, followers_count, profile_url
├── primary_platform: str                    — normalize_platform(platforms[0].name), for Pinecone filter
├── total_followers_count: int | None        — sum across all platforms, display/reference only
├── categories, content_style, content_style_v2 (ContentStyle)
├── audience_tags, audience_demographics (AudienceDemographics)
├── past_cpe, engagement_rate
├── contact                                  — email / phone / WeChat (non-URL)
│   [Media-specific]
├── outlet_type, beat, publish_frequency
│   [Vendor-specific]
├── service_type, region, capacity
│   [Placement-specific]
└── placement_type, location, audience_reach, available_formats
```

**Shared vs. client pool**:
- Default is `scope="shared"` — resource belongs to the agency's org-wide pool
- `scope="client"` — resource is exclusive to a specific client (e.g. contracted exclusively)
- The resource agent (`run_resource_agent`) queries **both** pools when running a pipeline: shared namespace `shared_{prefix}_{org_id}` + client namespace `{prefix}_{client_id}`
- UI scope toggle: "Agency Pool" tab fetches `scope=shared` (no client_id needed); "Client Resources" tab requires a client_id

**Pinecone namespaces**:
- Shared: `shared_resource_kol_{org_id}` / `shared_resource_media_{org_id}` / etc.
- Client: `resource_kol_{client_id}` / `resource_media_{client_id}` / etc.
- `resource_namespace(rtype, id_str, scope="client"|"shared")` resolves the namespace

**tier**: explicit only — filled by user or imported from Excel. Never auto-computed from follower count. `null` means unknown.

**Import**: `parse_resource_excel()` handles multi-platform strings automatically:
- `平台: 抖音+小红书` + `粉丝数: 抖音88万+小红书32万` → two PlatformEntry items with per-platform counts
- `平台: 抖音+小红书` + `粉丝数: 52万` (undivided) → two entries, per-platform count=None, total_followers_count=520000
- `序号` and other structural columns are in `KNOWN_IGNORE_COLUMNS` and are silently dropped before LLM inference
- `类型` → `categories` (content genre); `资源类型` → `type` (kol/koc/media)

**Pinecone filter**: `{"platforms": {"$in": ["xiaohongshu", "douyin"]}}` — array metadata, supports `$in` natively.

---

## Environment Variables

Create `.env` at the **repo root** (not inside `backend/`):

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=pitchcraft
JWT_SECRET_KEY=<run: python3 -c "import secrets; print(secrets.token_hex(32))">

# Token expiry (7 days = 10080 minutes)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080

# Optional — leave blank to disable
TAVILY_API_KEY=tvly-...
OPENAI_API_KEY=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
```

MongoDB, Redis, Celery, and the embedding service URLs are set automatically by Docker Compose.

---

## Internationalisation (i18n)

The app has **two independent language dimensions**. Do not conflate them.

### Dimension 1 — UI language (frontend display)

Implemented via **next-intl v3** with cookie-based locale switching (no URL prefix change).

| File | Role |
|------|------|
| `frontend/i18n/request.ts` | Server-side locale config — reads `NEXT_LOCALE` cookie, falls back to `zh` |
| `frontend/messages/zh.json` | Chinese UI strings |
| `frontend/messages/en.json` | English UI strings |
| `frontend/components/layout/LanguageSwitcher.tsx` | Globe icon button — sets cookie + `window.location.reload()` |

**Switching language:** Sidebar bottom → click "EN" / "中文". Sets `NEXT_LOCALE` cookie (1-year expiry), reloads page.

**Using translations in a page/component:**
```typescript
"use client";
import { useTranslations } from "next-intl";

export function MyComponent() {
  const t = useTranslations("myNamespace");
  return <button>{t("save")}</button>;
}
```

**Adding translations for a new page:**
1. Add a new namespace to both `messages/zh.json` and `messages/en.json`
2. Import and call `useTranslations("yourNamespace")` in the component
3. Replace hardcoded strings with `t("key")` calls
4. Rebuild: `make build s=frontend && make up`

**Existing namespaces** (don't duplicate keys that already exist):

| Namespace | Contents |
|-----------|----------|
| `nav` | Sidebar navigation labels |
| `common` | Shared actions: save, cancel, delete, confirm, upload, create, loading, etc. |
| `enums` | All enum display labels: `campaignType.*`, `budgetTier.*`, `recordType.*`, `confirmationStatus.*`, `confidence.*`, `pitchOutcome.*` |
| `campaigns` | Campaign KB list page + upload panel |
| `campaignRecord` | Campaign record review/edit/confirm page |
| `login` | Login / register page |
| `home` | Dashboard / home page |
| `clients` | Client list page |
| `clientDetail` | Client detail page (projects, brand profile, resource library tabs) |
| `projectDetail` | Project detail page (overview, proposals, archive tabs) |
| `pipeline` | Pipeline page + all HITL components (briefInput, hitlBrief, hitlStrategy, hitlMedia, hitlStructure, progress) |
| `proposals` | Proposal detail page |
| `files` | Asset library page |
| `resources` | KOL & Media library page |
| `research` | Research page |
| `analytics` | Analytics dashboard |

**Dynamic enum keys** — use try/catch for safety:
```typescript
const te = useTranslations("enums");
const label = (() => {
  try { return te(`campaignType.${value}` as Parameters<typeof te>[0]); }
  catch { return value.replace(/_/g, " "); }
})();
```

### Dimension 2 — Content language (brief / pipeline / PPT output)

Entirely independent from UI language. Controlled by `output_language` in `PipelineState`.

| Layer | Mechanism |
|-------|-----------|
| Brief + pipeline agent prompts | `detect_language(text)` → selects zh or en prompt variant |
| PPT output language | `output_language: "zh" \| "en" \| "auto"` in PipelineState; `"auto"` detects from brief |
| Campaign extraction | `detect_language(report_text)` per document — Chinese docs get Chinese prompts |
| Vector content | Propositions stored in source document language (Chinese doc → Chinese vectors) |
| Cross-lingual retrieval | BGE-M3 embeddings handle cross-lingual queries natively |

Prompt variants live in `backend/core/language/prompts.py` (pipeline agents) and inline in `backend/core/agents/campaign_extract.py` (KB extraction).

---

## Common Gotchas

1. **No hot-reload**: always `make build s=<service> && make up` after code changes.

2. **Use `apiFetch` not `fetch`**: raw `fetch` skips auth and won't handle 401 / token refresh.

3. **FormData uploads**: don't set `Content-Type` header manually — the browser sets it with the multipart boundary.

4. **FastAPI route order**: define specific sub-paths (`/pending`, `/search`, `/upload`) before `/{id}` catch-all routes.

5. **Background tasks vs sync**: confirmed record deletion runs Pinecone cleanup as a FastAPI `BackgroundTask` so the HTTP response returns immediately.

6. **Celery vs pipeline**: Celery async jobs (archive extraction, campaign indexing) log to `make logs s=worker`. The **proposal pipeline** runs in the backend via `BackgroundTasks` — use `make logs s=backend`. Campaign KB upload polls for results; pipeline uses WebSocket for progress + HTTP for HITL confirm.

7. **Pipeline HITL: HTTP confirm, not WebSocket**: never send `hitl_response` over WebSocket. Use `api.confirmNode()` → `POST /pipeline/{id}/confirm`. WebSocket is receive-only.

8. **Pipeline state: two Redis layers**: `AsyncRedisSaver` checkpoint (graph resume) vs `pipeline:{id}:state` (frontend GET). Don't assume one replaces the other.

9. **Pipeline confirm optimistic lock**: `POST /confirm` sets `running` before `add_task(resume_pipeline)`. Duplicate confirms while in flight get 400 (`status != paused`). Frontend also disables buttons via `confirming` state.

10. **Full file rewrite for large TSX files**: when making multiple edits to large files (> 300 lines), use `Write` with the entire new content rather than multiple `Edit` calls. Partial edits on large files can leave stale trailing content.

11. **ObjectId vs string IDs**: MongoDB `_id` is an `ObjectId` for most collections except `campaign_records` (which uses a plain UUID string). Use `bson.ObjectId(client_id)` when querying clients/projects/resources.

12. **i18n: `useTranslations` is a React hook** — it can only be called inside a component function body, not at module level. Badge helper functions that need translations must be converted to React components.

13. **i18n: `npm ci` in Dockerfile** — the Dockerfile uses `npm install --legacy-peer-deps` (not `npm ci`) because `npm ci` breaks when the local npm version differs from the container's npm version and generates an incompatible lockfile. Don't revert this to `npm ci`.

14. **Pipeline endpoints require org ownership**: all `/{pipeline_id}/*` endpoints call `_require_owner()` before any logic — returns 403 if `state.org_id != user.organization_id`. `/start` is exempt (creation, org_id comes from JWT).

15. **Pipeline process-restart recovery**: if `pipeline:{id}:status` is `running` for > 5 min, `GET /status` auto-calls `executor.recover()` which reads the LangGraph checkpoint. If `snapshot.next` is non-empty (graph at interrupt), status is restored to `paused` and `hitl_required` is re-broadcast. If empty, marked `error`. `POST /recover` also available for explicit recovery.

16. **Feedback rerun state fallback**: `POST /proposals/{id}/feedback` with `trigger_rerun=true` first tries Redis state; if expired (24h TTL), falls back to `ProposalVersionRepository.get_latest()` snapshot. Always check both before concluding state is unavailable.

---

## Testing

```bash
# Run all backend tests
pytest backend/tests/ -v

# Run a specific test file
pytest backend/tests/test_campaign_extract.py -v

# Run with coverage
pytest backend/tests/ --cov=backend --cov-report=html
```

Frontend has no test suite yet.

---

## Key Files for Each Domain

### Campaign KB
- `backend/core/models/campaign_record.py` — all Pydantic schemas
- `backend/core/agents/campaign_extract.py` — 3-call LLM extraction
- `backend/core/rag/campaign_index.py` — proposition indexing → Pinecone
- `backend/core/rag/campaign_retriever.py` — cross-campaign retrieval
- `backend/core/rag/archive_process.py` — Celery task: parse → extract → save
- `backend/api/v1/endpoints/campaigns.py` — REST API
- `frontend/app/campaigns/page.tsx` — upload + list UI
- `frontend/app/campaigns/[recordId]/page.tsx` — review/edit/confirm UI

### Pipeline
- `backend/core/graph/pipeline.py` — LangGraph `StateGraph`, 5 `interrupt()` HITL nodes, conditional Resource skip
- `backend/core/graph/executor.py` — `start()` / `resume_pipeline()` / `_prime_checkpointer_for_rerun()`; `AsyncRedisSaver`
- `backend/core/graph/state.py` — `PipelineState` schema, `RequestBudget`
- `backend/api/v1/endpoints/pipeline.py` — `POST /start`, `POST /confirm`, `POST /rerun`, GET data endpoints
- `backend/api/v1/websocket.py` — receive-only WebSocket progress broadcast
- `backend/api/v1/endpoints/proposals.py` — post-completion feedback rerun → `executor.start(state, start_from)`
- `frontend/app/pipeline/page.tsx` — pipeline UI; HITL via `api.confirmNode()` (HTTP)
- `frontend/hooks/usePipelineSocket.ts` — WebSocket receive-only; dispatches Redux on progress events
- `frontend/components/gallery/GalleryView.tsx` — HITL 5 gallery confirm with `flagged_indices`

### Resource Library
- `backend/core/models/resource.py` — Resource / PlatformEntry / ResourceType schemas; `parse_follower_count`, `normalize_platform`
- `backend/core/rag/resource_import.py` — Excel import: `parse_resource_excel`, `_build_platforms`, `resource_to_text`, `HEADER_ALIASES`, `KNOWN_IGNORE_COLUMNS`
- `backend/core/agents/resource.py` — resource retrieval agent; `_build_metadata_filter` (Pinecone platform filter)
- `backend/api/v1/endpoints/resources.py` — REST API (CRUD + import preview/confirm)
- `frontend/app/resources/page.tsx` — resource list UI + Excel import flow
- `frontend/store/resourcesSlice.ts` — Redux slice + Resource TypeScript interface

### Auth
- `backend/api/v1/endpoints/auth.py` — register/login/refresh
- `backend/api/v1/permissions.py` — `get_current_user` dependency
- `frontend/lib/api.ts` — `apiFetch`, token storage, refresh logic
