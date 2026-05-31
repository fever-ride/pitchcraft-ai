# Brand Library

**Last updated**: 2026-05-30

---

## Overview

The Brand Library is the persistent, client-level knowledge store that tells agents *who this brand is* and *how it has communicated in the past*. It has three layers that serve different purposes:

| Layer | Storage | What it holds | When used |
|-------|---------|---------------|-----------|
| BrandProfile | MongoDB (1 doc per client) | Structured brand identity: positioning, personality, tone rules, forbidden directions, key messages, competitive position | Loaded directly into every agent prompt that needs brand context |
| Brand Spec (raw docs) | Pinecone `brand_spec_{client_id}` | Full text of brand handbooks, VI guides, Tone of Voice documents | Vector search fallback if no BrandProfile; supplements BrandProfile with detailed examples |
| Brand History | Pinecone `brand_style_{client_id}` | Past pitch proposals, historical copy, social content | Style reference for Slide Content Agent |

---

## Layer 1: BrandProfile (MongoDB)

### Why MongoDB, not Pinecone?

A brand's core identity is a *single authoritative document*, not a large corpus to search through. Storing it in MongoDB means:
- Always loaded (no retrieval threshold to miss)
- Structured fields (tone_principles, forbidden_directions) can be used as hard constraints in brand checks
- No semantic search overhead — the full profile is injected directly into the prompt

### Schema

```
brand_profiles collection:
  client_id           (1:1 with clients)
  brand_name
  positioning         "what the brand stands for, for whom, vs whom"
  target_audience
  personality         [str]  e.g. ["权威", "亲民", "专业"]
  tone_principles     [str]  e.g. ["避免娱乐化表达", "不用对比广告"]
  forbidden_directions [str] explicitly banned creative directions (from brand spec)
  key_messages        [str]  core points the brand always wants to convey
  competitive_position str   how the brand differentiates vs competitors
  approved_directions [str]  auto-populated from client feedback ($addToSet)
  rejected_directions [str]  auto-populated from client feedback ($addToSet)
  updated_at / created_at
```

### How it's populated

**Path 1: Manual form** — AE fills in fields via the Brand Profile tab in the client page.

**Path 2: LLM extraction** — AE pastes text from a brand document → POST /brand-profile/extract → LLM (haiku model) extracts structured fields → AE reviews the draft → applies to form → saves.

**Path 3: Feedback loop** — When client feedback is recorded (approved/rejected directions), those are automatically `$addToSet`-ed into the profile's `approved_directions` / `rejected_directions` fields. No manual action needed.

> **Note:** `forbidden_directions` and `rejected_directions` are different things:
> - `forbidden_directions`: from the brand spec document (e.g. "never use competitor names directly") — set by AE
> - `rejected_directions`: from specific proposal feedback (e.g. "client rejected the 'sports science' angle") — auto-accumulated

### How agents use it

**Strategy Phase 1** — BrandProfile is loaded and injected as a structured block before the Pinecone brand materials:
```
[Brand Profile: {brand_name}]
Positioning: ...
Target Audience: ...
Tone Principles:
  - ...
Forbidden Directions (from brand spec):
  - ...
Previously Approved Directions (from client feedback):
  - ...
Previously Rejected Directions (from client feedback):
  - ...

[Brand Materials from Library]
{pinecone results}
```

**Brand Consistency Check** — If the profile has `tone_principles` or `forbidden_directions`, the check uses the structured profile instead of vector search. Falls back to Pinecone if neither field is populated.

---

## Layer 2: Brand Spec Docs (Pinecone `brand_spec_{client_id}`)

### What goes here

- Brand handbooks (text-extractable)
- Tone of Voice guides
- Brand positioning documents
- Approved creative directions (embedded by the feedback loop with `[Approved direction]` prefix)

### Chunk strategy

256-token chunks (short, for high precision on normative rules).

### When used

- Supplementary context in Strategy Phase 1 (after BrandProfile)
- Brand consistency check fallback (when no structured BrandProfile exists)

---

## Layer 3: Brand History (Pinecone `brand_style_{client_id}`)

### What goes here

- Past pitch proposals (PPTX/PDF)
- Historical copy (social posts, press releases, campaign scripts)

### Chunk strategy

- Proposals: 512-token chunks
- Copy: 128-token chunks (sentence boundaries)

### When used

Style reference for Slide Content Agent — retrieves how this brand has written copy in the past.

---

## Feedback Loop Integration

```
AE submits feedback (approved_directions + rejected_directions)
        ↓
approved_directions:
  ├── Embed to Pinecone brand_spec_{client_id}  (vector search available)
  └── $addToSet → BrandProfile.approved_directions  (direct in-prompt)

rejected_directions:
  ├── Stored in feedback collection  (Strategy Phase 2 reads last 10 as constraints)
  └── $addToSet → BrandProfile.rejected_directions  (direct in-prompt, Phase 1 + brand_check)
```

The `$addToSet` operation means directions are never duplicated in the profile even if the same direction appears in multiple feedback submissions.

The BrandProfile is only enriched — it is never overwritten by the feedback loop. Only the AE's manual save (PUT /brand-profile) can change the core identity fields.

---

## File Types and Namespace Routing

| File type | file_type enum | Pinecone namespace |
|-----------|---------------|-------------------|
| Brand spec | `brand_spec` | `brand_spec_{client_id}` |
| Historical proposal | `brand_history_proposal` | `brand_style_{client_id}` |
| Historical copy | `brand_history_copy` | `brand_style_{client_id}` |

---

## Limitations and Known Constraints

- **Image-heavy documents**: Brand VI manuals that are primarily image-based (e.g. McDonald's visual identity guide) yield very little text on extraction. LLM Vision can extract qualitative style rules reliably but technical specs (exact hex codes, pixel measurements) are unreliable. For now the system assumes text-based brand spec input; VI manuals should be summarized manually before uploading.

- **BrandProfile requires AE initialization**: The feedback loop only *enriches* an existing profile — it does not create one from scratch. If no BrandProfile exists, agents fall back to Pinecone retrieval.
