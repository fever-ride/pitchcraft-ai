# Pitchcraft — Claude Code Guide

This file is the primary reference for Claude Code sessions working on this codebase.

---

## Project Overview

Pitchcraft is an AI-powered proposal automation platform for PR/marketing agencies. It converts a client brief into a presentation-ready PowerPoint deck using an 8-agent LangGraph pipeline with human-in-the-loop checkpoints.

**Stack:**
- Backend: FastAPI + LangGraph + Celery + MongoDB + Pinecone
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
| `/pipeline` | `app/pipeline/page.tsx` | Run a new proposal pipeline; all 6 HITL checkpoints |
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

## Backend Endpoints

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

6. **Celery task visibility**: async processing only shows up in `make logs s=worker`. The frontend polls for results rather than listening to a webhook.

7. **Full file rewrite for large TSX files**: when making multiple edits to large files (> 300 lines), use `Write` with the entire new content rather than multiple `Edit` calls. Partial edits on large files can leave stale trailing content.

8. **ObjectId vs string IDs**: MongoDB `_id` is an `ObjectId` for most collections except `campaign_records` (which uses a plain UUID string). Use `bson.ObjectId(client_id)` when querying clients/projects/resources.

9. **i18n: `useTranslations` is a React hook** — it can only be called inside a component function body, not at module level. Badge helper functions that need translations must be converted to React components.

10. **i18n: `npm ci` in Dockerfile** — the Dockerfile uses `npm install --legacy-peer-deps` (not `npm ci`) because `npm ci` breaks when the local npm version differs from the container's npm version and generates an incompatible lockfile. Don't revert this to `npm ci`.

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
- `backend/core/graph/pipeline.py` — LangGraph node definitions
- `backend/core/graph/executor.py` — run/rerun logic
- `backend/core/graph/state.py` — PipelineState schema
- `frontend/app/pipeline/page.tsx` — pipeline UI with all HITL checkpoints

### Auth
- `backend/api/v1/endpoints/auth.py` — register/login/refresh
- `backend/api/v1/permissions.py` — `get_current_user` dependency
- `frontend/lib/api.ts` — `apiFetch`, token storage, refresh logic
