# Campaign Knowledge Base

A structured memory system that accumulates decision records from past campaigns and makes them available to every planning agent in the pipeline — turning each completed project into reusable institutional knowledge.

---

## Why This Exists

An experienced media planner at an ad agency carries years of pattern knowledge in their head: which KOL tier ratio works for beauty launches, how a particular client responds to bold creative, what deck structure wins pitches for automotive brands. When they leave, that knowledge leaves with them.

This module captures that knowledge systematically. Every archived project produces a structured record. After 20+ projects, the system's recommendations are informed by the agency's own real outcome data — not generic industry frameworks.

**The competitive moat is not the technology. It is the accumulated records.**

---

## Architecture

Three storage layers, each serving a different purpose:

```
Layer 1: campaign_records (MongoDB)
  Full structured record — 50+ fields across 5 dimensions
  Used for: human review, editing, and as the source of truth
  Scope: one record per project

Layer 2: campaign_propositions (MongoDB)
  Atomic, self-contained insight statements extracted from Layer 1
  e.g. "[美妆 | launch | 200万 | Z世代] KOC tier 占预算10%但贡献60%互动量"
  Used for: traceability — each proposition links back to its parent record
  Scope: 8–15 propositions per record

Layer 3: campaign_knowledge_{org_id} (Pinecone)
  Vector embeddings of Layer 2 propositions, with campaign metadata attached
  Used for: semantic search at retrieval time
  Scope: all confirmed records for the org, in one shared namespace
```

**Why propositions instead of embedding the full record?**

A single 200-word summary embedding dilutes specific signals. "KOC tier drove 60% engagement at 10% budget" is lost inside a general campaign summary. Atomic propositions give each insight its own vector — a query about KOC budget allocation matches precisely, not by accident.

**Why the meta prefix on each proposition?**

```
Without:  "KOC tier drove 60% engagement at 10% budget"
          → embedding captures the fact, but not when it applies

With:     "[美妆 | launch | 200万 | Z世代] KOC tier drove 60% engagement at 10% budget"
          → embedding captures both the fact AND its applicability conditions
```

A query about "beauty launch KOC effectiveness" matches strongly. A query about "automotive branding KOC" does not — even though both mention KOC.

---

## Two Record Types

The same pipeline handles both pitch decks and recap reports. `record_type` is **auto-detected** by the Background LLM call — no manual tagging needed.

| | Proposal (`record_type = "proposal"`) | Campaign (`record_type = "campaign"`) |
|---|---|---|
| **Source** | Pitch deck submitted to client | Post-campaign recap report |
| **Contains** | Strategy, channel plan, deck structure | Everything + execution details + real KPI data |
| **Missing** | Execution data, outcome metrics | — |
| **Extra field** | `pitch_outcome` (won / lost / unknown) | — |
| **LLM calls** | 2 (Background + Execution; no Outcome call) | 3 (Background + Execution + Outcome) |
| **Value** | Shows what strategic thinking won client approval | Shows what actually worked |

**Why proposals matter:** This product's output IS a proposal. Past proposals showing what angles got client sign-off are the most directly relevant reference data — more so than campaign recaps for pure strategic framing.

**`pitch_outcome`:** The proposal document itself doesn't say whether the pitch was won or lost. An AE marks this manually at the confirmation step. Cost: one click. Value: won proposals are prioritised in retrieval; lost proposals are returned as contrast reference only.

**Why skip the Outcome call for proposals?** Proposals have no execution results — running an Outcome extraction call returns empty fields. Empty fields count as a low-confidence call, which drags `overall_confidence` from `high` down to `low` even when Background and Execution extracted everything correctly. Skipping the call keeps confidence accurate.

---

## Data Flow

```
1. Upload
   POST /api/v1/projects/{id}/archive
   Accepts: PDF, PPTX, DOCX (recap report or proposal deck)
   Triggers: Celery async task

2. Parse & Clean
   parser.py: extract text per page/slide with location metadata
   Boilerplate removal: lines appearing on >30% of pages stripped (headers, footers, page numbers)
   Handles both Chinese (第3页) and English (Page 3) page-number patterns

3. LLM Extraction — 3 parallel calls
   Call 1 (Strategy Analyst): meta + strategy_decisions + communication_plan + deck_info
     → reads first 40,000 chars
     → auto-detects record_type (proposal / campaign)
   Call 2 (Integrated Marketing Expert): media_plan + execution (incl. PR activities)
     → reads first 40,000 chars
     → handles advertising-heavy, PR-heavy, or mixed campaigns
   Call 3 (Evaluation Expert): outcome only
     → SKIPPED for proposals (no results to extract)
     → reads last 20,000 chars for campaigns (results are back-loaded)
     → fallback: if key fields empty, retries with preceding 20,000-char section

   client_learnings: NOT extracted by LLM — filled manually by AE at confirmation.
   Confidence: overall = worst of participating calls (high / partial / low)
   Partial failure: if one call fails, others still contribute

4. Store for Review
   MongoDB campaign_records, status = pending_confirmation
   Accessible at /campaigns (pending tab)

5. Human Confirmation
   AE reviews extracted record, corrects errors, fills gaps
   Sets overall_rating (1–5)
   For proposals: sets pitch_outcome (won / lost / unknown)
   Fills client_learnings manually (decision style, approved/rejected directions)
   Submits → status = confirmed → triggers proposition indexing

6. Proposition Indexing (background task)
   LLM decomposes confirmed record into 8–15 atomic propositions
   Each proposition prefixed with [industry | type | budget | audience]
   Stored in MongoDB campaign_propositions (traceability)
   Embedded via BGE-M3 → upserted to Pinecone campaign_knowledge_{org_id}
   Pinecone metadata per vector: campaign_record_id, campaign_type, industry,
     budget_tier, record_type, pitch_outcome
```

---

## How Agents Use It

Each agent calls `retrieve_campaign_knowledge()` with a profile that controls what it gets.

**Retrieval flow:**
```
1. Semantic search on proposition vectors (Pinecone)
2. Group matched propositions by campaign_record_id
3. Deduplicate: if same project has both proposal + campaign, campaign is primary;
   proposal demoted to secondary with note
4. Fetch full structured modules from MongoDB (only the modules each profile needs)
5. Self-verification: LLM judges whether matched campaigns are actually relevant
   → sufficient: return results
   → partial: return with caveat note
   → insufficient: return empty — agent falls back to prompt-embedded knowledge
```

**Per-agent profiles:**

| Agent | Profile | top_k | Modules returned | record_type preference |
|---|---|---|---|---|
| Strategy P2 | `strategy_reference` | 6 | strategy_decisions, communication_plan, outcome | both |
| Media Planning | `media_planning` | 15 | media_plan, execution, outcome | campaign only |
| Resource Agent | `resource_reference` | 8 | execution, outcome | campaign preferred |
| Deck Orchestrator | `deck_reference` | 4 | deck_info, communication_plan | proposal preferred |
| Brief Analyzer | `brief_reference` | 4 | client_learnings, meta | both |

**Context headers in agent prompts:**
```
[历史结案: 美妆 | launch | 500k_2m | Z世代]
  strategy_decisions: {...}
  outcome: {"KOC互动率": "8.3%"}

[历史提案·中标: 美妆 | launch | 100k_500k | 都市女性]
  strategy_decisions: {...}
  deck_info: {...}

[历史提案·结果未知: 科技 | branding | 2m_5m | 年轻男性]
  [注意: 同一项目已有结案数据，此提案仅供策略思路参考，数字为预估值]
  strategy_decisions: {...}
```

Agents receive clear provenance labels — no prompt instruction needed to distinguish estimated vs validated data.

---

## Self-Verification (Quality Gate)

When the knowledge base is sparse (first 5–10 records), Pinecone always returns top-k matches regardless of actual relevance. Without a quality gate, a beauty launch would be cited as reference for every new project simply because it's the only record.

After retrieval, a lightweight LLM call judges relevance:

```
Matching dimensions: industry | campaign_type | budget_tier | target_audience
≥ 3 match → sufficient  → use normally
= 2 match → partial     → use with caveat note in context
< 2 match → insufficient → drop results entirely; agent uses prompt knowledge only
```

Verification failure (LLM error) defaults to returning results unfiltered — it is a best-effort quality gate, not a hard dependency.

---

## Language Handling

Source documents may be Chinese, English, or mixed. Chinese ad/PR reports routinely contain English industry terms (KOL, KOC, ROI, CPE, OOH, TVC).

- All LLM prompts are bilingual (zh/en dict). Language auto-detected per document via `detect_language()`.
- Propositions are generated in the source language. English terms in Chinese documents are preserved as-is.
- Retrieval queries from agents may be Chinese, English, or mixed. BGE-M3 embeddings handle cross-lingual matching — a Chinese query matches Chinese propositions with embedded English terms naturally.
- Verification prompt language is detected from the query string.

---

## Current Status

### Completed

- [x] `CampaignRecord` schema — 50+ fields, 5 knowledge dimensions
- [x] `campaign_subtype` free-text field alongside `campaign_type` enum (dual-field: enum for filtering, subtype for semantic richness)
- [x] `client_name` field in `CampaignMeta` (LLM-extracted brand name, distinct from `client_id` FK)
- [x] 3-parallel LLM extraction pipeline with per-call text windowing
- [x] `record_type` auto-detection in Background call (LLM judges proposal vs campaign from document content)
- [x] 2-call extraction for proposals (Background + Execution only; Outcome call skipped — no results to extract)
- [x] Text cleaning: PDF boilerplate removal, minimum chunk token threshold
- [x] `pitch_outcome` (won / lost / unknown) field — schema and API support complete; AE sets value at confirmation step (frontend dropdown not yet built — see Pending)
- [x] `page_count` → `slide_count` passthrough: file parser page count fills `deck_info.slide_count` when LLM doesn't extract it
- [x] MongoDB storage with explicit string `_id` and `org_id` isolation
- [x] Human confirmation API and frontend (list page, detail/edit page)
- [x] Proposition extraction + contextual meta prefix + Pinecone upsert
- [x] `campaign_subtype` in proposition meta prefix (fallback to `campaign_type`)
- [x] `record_type` and `pitch_outcome` in Pinecone vector metadata
- [x] 5 per-agent retrieval profiles
- [x] Two-level retrieval: proposition matching → full module fetch
- [x] Same-project deduplication (campaign wins over proposal)
- [x] Context header labels: `[历史结案]` / `[历史提案·中标]` / `[历史提案·未中标]`
- [x] Self-verification (5.8): sufficient / partial / insufficient verdict
- [x] All 5 agents integrated: Strategy P2, Media Planning, Resource, Deck, Brief Analyzer
- [x] Integration test script: `scripts/test_campaign_kb_pipeline.py` (all 9 steps verified end-to-end)

### Pending

- [ ] Metadata filter pass-through: agents currently don't pass `metadata_filter` to retrieval — semantic search runs without business-condition pre-filtering (industry, campaign_type, budget_tier)
- [ ] Frontend: `pitch_outcome` selector on confirmation page
- [ ] Frontend: `client_learnings` manual input section on confirmation page
- [ ] Hybrid search: sparse + dense vectors (BGE-M3 supports sparse; needs Pinecone config)
- [ ] Retrieval quality feedback: track HITL edit distance vs retrieved records (5.7)
- [ ] Distilled insights: auto-distill patterns when 10+ confirmed records accumulate (5.9)
- [ ] Confirmation UX polish: guided wizard, field-level confidence indicators

### Known Limitations

- **Sparse knowledge base.** The full pipeline is verified end-to-end (Steps 1-9, including Pinecone upsert and retrieval). Self-verification and cross-campaign retrieval only become meaningful after the first 5–10 confirmed records are accumulated.
- **Image-heavy documents extract poorly.** Many proposal decks are predominantly visual. PDF parsing captures text only; images, charts, and designed layouts are invisible to the extractor. Workaround: upload PPTX instead of PDF — python-pptx extracts all text boxes including those inside designed slides. OCR is not planned for the current phase.
- **`client_learnings` not auto-extracted.** This information doesn't appear in formal recap reports. AEs fill it manually. Quality depends on AE discipline.
- **Single-pass extraction.** Very long or badly structured reports may have information scattered in ways the text windowing misses. The middle-section fallback for Call 3 mitigates the most common case.

---

## Immediate Next Steps

1. **Complete Step 8: Pinecone upsert** — get Pinecone API key (free tier at app.pinecone.io), create index (1024 dims for BGE-M3), add `PINECONE_API_KEY` to `.env`, start embedding service with `docker compose up -d embedding`, re-run test script.

2. **Test retrieval end-to-end** — once Step 8 is done, run `retrieve_campaign_knowledge()` with a sample query matching the 安踏 record. Verify proposition matching → module fetch → self-verification.

3. **Add metadata filter to agent calls** — Strategy P2 and Media Planning should pass `industry` and `campaign_type` from the current brief so retrieval pre-filters before semantic search.

4. **Test with a proposal document** — verify 2-call path, `record_type=proposal` auto-detection, and `confidence` stability (no empty Outcome call dragging it down).

5. **Add `pitch_outcome` to confirmation UI** — low-cost, high-value: one dropdown field on the existing confirmation page.

---

## File Map

```
backend/core/models/campaign_record.py     Schema definitions
backend/core/agents/campaign_extract.py    3-call LLM extraction
backend/core/rag/archive_process.py        Celery task: upload → extract → store
backend/core/rag/campaign_index.py         Proposition extraction + Pinecone upsert
backend/core/rag/campaign_retriever.py     Retrieval profiles + self-verification
backend/api/v1/endpoints/campaigns.py      Confirmation API
backend/api/v1/endpoints/projects.py       Archive upload endpoint
frontend/app/campaigns/                    Confirmation UI
frontend/store/campaignsSlice.ts           Redux state
```
