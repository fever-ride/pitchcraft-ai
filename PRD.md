# PRD: Pitchcraft

**Version**: v0.4
**Status**: Draft
**Last updated**: 2026-05

---

## 1. Background

### 1.1 What is Pitchcraft

An AI proposal assistant for Account teams at PR and marketing agencies. It uses a multi-agent architecture to automate the core pitch workflow: understanding client briefs, generating strategy, writing copy, analyzing competitors, matching external resources, and producing a ready-to-use PowerPoint deck.

### 1.2 Problem

Account teams face four pain points during pitch season:

- **Time pressure**: 3-5 days from brief to delivery
- **Scattered information**: Brand assets, competitor intel, and KOL data live in different places
- **Repetitive structure work**: Every pitch rebuilds similar slide frameworks from scratch
- **High alignment cost**: Strategy, creative direction, and execution feasibility must all agree

### 1.3 Target Users

**Primary user**: Account Executive / Account Manager at agency-side PR or marketing firms.

**User traits**:

- Strong brand communications instincts, weak technical background
- Time-sensitive, needs fast output
- Expects deliverables that are usable immediately or with minimal edits
- Manages multiple client accounts simultaneously
- Multiple Accounts at the same agency may collaborate on one client
- Works in Chinese or English (system supports both)

### 1.4 Multi-Tenancy and Collaboration

The system uses the agency (company) as the top-level tenant and supports multi-Account collaboration.

**Data hierarchy**:

```
Organization (Agency)
    ↓
Client ← Brand Library lives here, visible to all org members
    ↓
Project ← Can be restricted to assigned Accounts only
    ↓
Proposal ← Individual Account's work product
```

**Permission tiers**:

| Action | Account | Lead Account | Admin |
|--------|---------|--------------|-------|
| View Brand Library | Yes | Yes | Yes |
| Upload to Brand Library | Yes | Yes | Yes |
| Delete Brand Library files | No | Yes | Yes |
| Modify client default deck structure | No | Yes | Yes |
| View all projects | No | Yes | Yes |

**Concurrency handling**:

- Duplicate filename upload: auto-suffix the later upload, prompt user to confirm replacement
- File deletion: soft-delete (`deleted=true`), does not affect running pipelines
- Deck structure modification: pipeline snapshots the structure at start time, later edits do not affect in-progress runs

---

## 2. Core Modules

### 2.1 File Management

Accounts organize two types of files before pitching. The system manages them separately.

#### Brand Library (long-term, cross-project)

Persistent brand assets for a client, reused across projects.

| Type | Examples | Purpose |
|------|----------|---------|
| Brand specs | VI guide, brand book, Tone of Voice | Constraints for content generation |
| Historical proposals | Past campaign decks, strategy docs | RAG style reference |
| Brand content | Past copywriting, social posts | Copy style learning |

#### Project Library (per-project, archived after completion)

Files specific to one pitch.

| Type | Examples | Purpose |
|------|----------|---------|
| Requirements | Client brief, meeting notes | Brief Analyzer input |
| Visual references | Moodboard, competitor screenshots | Visual direction (Phase 2) |
| Competitor materials | Competitor copy, competitor deck screenshots | Research input |

**Technical notes**:

- Spec and text files go through the standard RAG pipeline
- Visual references require multimodal processing, deferred to Phase 2

---

### 2.2 Brief Analyzer (Entry Point)

Users input client requirements in natural language. The system extracts structure and fills information gaps.

**Input**: Free-form brief (can be informal, incomplete)

**Processing logic**:

```
Extract known fields
├── Brand / client name
├── Campaign theme or direction
├── Target audience
├── Channels
├── Budget range
├── Timeline
└── Campaign objective (awareness / conversion / branding)

Flag ambiguous language
├── Unclear intent ("make it youthful", "something warm")
└── Unresolved references ("similar to last time")

Detect required gaps
└── Generate clarification questions for missing critical fields

Decide readiness
├── Sufficient info → enter agent pipeline
└── Insufficient → return structured follow-up questions
```

**Output**: Structured brief card + clarification list (if needed)

---

### 2.3 Research Agent

Research is the most time-consuming part of pitching and the highest-value automation target.

#### Research dimensions

| Dimension | Content | Data source |
|-----------|---------|-------------|
| Brand positioning | Competitor value propositions, slogans | Web search, official sites |
| Communication strategy | Recent campaigns, messaging cadence | News, public reports |
| Social media performance | Platform content style, engagement data | User-uploaded screenshots (P1) / third-party APIs (P2) |
| Visual style | Color palette, design language | User-uploaded competitor screenshots |
| Internal history | Whether past analysis exists for this competitor | Internal RAG library |

#### Data acquisition strategy

**Phase 1**:

- Real-time web search: brand news, public reports, official sites
- User-uploaded competitor screenshots, analyzed by the system
- Internal history file retrieval

**Phase 2**:

- Third-party social data platforms (locale-specific: e.g. Chanmama/Feigua for China, Sprout Social/Brandwatch for global)
- Multimodal visual style analysis

**Output**: Structured competitor analysis report, insertable directly into the pitch deck.

---

### 2.4 Strategy Agent

Generates the strategy framework in two phases based on the brief and research results.

#### Phase 1: Insights (runs in parallel with Research)

Does not depend on competitor data. Uses Brief + Brand Library only:

- Audience insight (target segment analysis)
- Brand direction (initial strategic angle based on brand assets)

#### Phase 2: Strategy (runs after Research completes)

Integrates competitor research to generate the full strategy:

- Campaign theme / Big Idea
- Communication logic (why this approach)
- Channel mix recommendation
- Budget allocation (auto-distribute across channels)
- KPI recommendations

**Design rationale**: Competitor research directly affects differentiation positioning, but audience insights and brand direction do not depend on competitors. The two-phase design maintains strategy quality while reducing wait time through parallelism.

**Brand consistency check**: After Phase 2 completes, the system compares the strategy against the Brand Library to detect conflicts with brand tone.

---

### 2.5 Resource Agent (Pluggable)

Different project types require different external resources. KOLs are one type; PR projects need media outlets, offline events need vendors, ad campaigns need media placements. Resource matching is designed as an independent, pluggable agent rather than hardcoded into the pipeline.

#### Trigger logic

```
Strategy Agent outputs channel mix
        ↓
Resource Agent determines which resource types are needed
        ├── Social channels → query KOL/KOC database
        ├── PR/media channels → query media resource database
        ├── Offline channels → query vendor database
        ├── Ad placement channels → query placement database
        └── No external resources needed → skip entirely
```

**Design principle**: Resource Agent is optional. Not every project triggers it. Adding a new resource type only requires extending the database and tag schema, not modifying agent logic.

#### Resource databases

**KOL/KOC Database** (social channels)

| Field | Content |
|-------|---------|
| Basic info | Platform, handle, follower tier, content direction, MCN |
| Audience profile | Age/gender/region distribution |
| Collaboration history | Past brands, content formats, performance data |
| Pricing reference | Historical price range |
| Tags | Industry / content style / audience traits |

Data source: manual entry or Excel bulk import initially; locale-specific third-party APIs in Phase 2 (e.g. Chanmama/Feigua for China market, CreatorIQ for global).

---

**Media Resource Database** (PR channels)

| Field | Content |
|-------|---------|
| Basic info | Outlet name, type (print/online/vertical), coverage domain |
| Contact | Journalist/editor name, beat, contact info |
| Publish types | Press release, interview, review, content partnership |
| Pricing reference | Commercial publishing price range |
| Tags | Industry / audience / region |

---

**Vendor Database** (offline channels)

| Field | Content |
|-------|---------|
| Basic info | Company name, service type (venue/setup/event execution/photography) |
| Past work | Brands served, project types, quality rating |
| Pricing reference | Service price range |
| Tags | Industry / region / scale |

---

**Placement Database** (ad channels)

| Field | Content |
|-------|---------|
| Basic info | Placement type (OOH/elevator/magazine/cinema), cities covered |
| Details | Location/slot, audience size, availability |
| Pricing reference | Rate card, discount range |
| Tags | Audience profile / region / scenario |

#### Unified data model

All four resource types share the same underlying structure. Only the tag schema differs:

```
Resource
├── id
├── type              # kol / media / vendor / placement
├── name
├── tags              # tag schema varies by type
├── pricing           # price reference
├── collaboration_history
└── metadata          # type-specific fields
```

---

### 2.6 Deck System

Copywriting in the pitch phase serves individual slides, not standalone deliverables. Copy generation is built into the Deck system rather than existing as a separate agent. The Deck system has four sub-agents:

```
Deck Orchestrator
    ├── Slide Content Agent     Content generation (including copy)
    ├── Narrative Agent         Coherence suggestions (non-blocking, background)
    └── PPT Builder             Technical assembly
```

---

#### 2.6.1 Deck Orchestrator

**Role**: Decides which slides the deck needs, their order, and content depth per slide based on project type and user settings.

**Structure priority** (highest to lowest):

```
Project-level override ← user adjusts for this specific pitch only
        ↓
Client-level default ← user sets a custom template for this client
        ↓
Global default ← built-in, works out of the box
```

Default structures vary by project type:

| Project type | Key slide differences |
|-------------|----------------------|
| Social media pitch | KOL strategy page, per-platform execution pages |
| PR pitch | Media matrix page, press release cadence page |
| Integrated marketing pitch | Full-channel coverage, budget allocation overview page |
| Brand refresh pitch | Brand diagnosis page, before/after comparison page |

**Checkpoint (Node 3)**: After the Orchestrator outputs the slide structure, it pauses for user confirmation. Users can add, remove, or reorder slides before generation begins.

---

#### 2.6.2 Slide Content Agent

**Role**: Generates content for each slide including copy, data points, tables, and bullet points.

| Slide type | Source | Generated content |
|-----------|--------|-------------------|
| Market and competitor insights | Research Agent output | Competitor comparison, market trend highlights |
| Audience insights | Brief + web search | Audience persona, insight distillation |
| Strategy framework / Big Idea | Strategy Agent output | Core communication logic, theme |
| Creative direction | Strategy + RAG history | Sample slogans, creative concept descriptions |
| Channel execution plans | Strategy output | Per-channel content strategy, execution cadence |
| External resources | Resource Agent output | KOL list / media matrix / vendor recommendations |
| Budget allocation | Strategy output | Allocation ratios, cost breakdowns |
| Timeline | Brief timeline + Strategy cadence | Campaign Gantt chart |
| KPIs and projections | Strategy output | KPI targets, benchmark reference data |

**Style enforcement**: When generating copy, the agent retrieves Tone of Voice and historical copy from the Brand Library to match brand tone.

**Checkpoint (Node 4), Gallery Review mode**:

All slides are presented together as structured content cards (title, copy, bullets, data). This is not rendered PPT. PPT layout happens after confirmation in PPT Builder. Slides stream in as they complete, so users can start reviewing before all slides are done.

Users browse freely (not forced sequential) and mark each slide: confirm / flag for revision (with notes) / skip. After marking, all flagged slides regenerate in batch and return to the Gallery for re-review.

**Layout**:
- Left: slide thumbnail navigation (check = confirmed, warning = flagged, blank = unreviewed)
- Right: current slide full preview + Narrative suggestions (if any)
- Bottom: progress bar + two exit buttons ("Process flagged slides" / "Confirm all, generate PPT")

**Streaming**: Each slide pushes to the Gallery immediately upon completion. Users can review finished slides while later ones are still generating.

---

#### 2.6.3 Narrative Agent (Non-blocking Advisor)

**Role**: Checks whether the full deck tells a coherent, persuasive story. Presents findings as suggestions, not directives.

This is the most PR/marketing-judgment-heavy component. It evaluates the proposal as a persuasion structure, not individual slide correctness. It does not control the flow. The user has final say.

**Checks**:

```
Is the insight → strategy → execution logic chain clear?
    ├── Does the insight support the strategy direction?
    │   (Can't have insight "Gen Z values individuality" + strategy "compete on price")
    ├── Can the execution plan deliver the strategy?
    │   (Can't have strategy "emotional resonance" + execution all hard ads)
    ├── Do resource choices match audience and channels?
    │   (Can't target middle-aged audience + all KOLs are Gen Z influencers)
    └── Does budget allocation match strategy priorities?
        (Can't say social is the priority + social gets 10% of budget)
```

**Execution**: Triggers in the background after Slide Content Agent completes. Does not block the flow. Results appear as a suggestion panel in the Node 4 Gallery.

**Output**: Structured suggestion list. Each suggestion references a specific page number and describes the issue. Users can:
- Ignore suggestions and confirm directly
- Accept suggestions and trigger page regeneration
- Partially accept

**Design principle**: Narrative Agent plays the role of a colleague glancing over your shoulder, not a gatekeeper. It never blocks, never auto-rejects, never loops.

---

#### 2.6.4 PPT Builder

**Role**: Pure technical execution. Assembles all content into a `.pptx` file. Makes no business judgments.

- Uses `python-pptx` to fill content into templates
- Fixed templates initially; Phase 2 supports client VI color/font customization
- Provides a read-only web preview + `.pptx` download after generation
- **Not a review checkpoint**: content was already confirmed at Node 4. PPT Builder produces deterministic output.
- Preview page includes a "Layout issue? Give feedback" link for reporting template/layout problems (does not trigger content rerun)

---

### 2.7 Version Management

Proposals typically go through multiple revisions. The system tracks every version.

**Features**:

- Auto-save a new version after each regeneration or manual edit
- Version diff (what changed between versions)
- One-click rollback to any previous version
- Version notes (why this revision was made)

---

### 2.8 Client Feedback and Iteration

Client feedback is not just a record. It is a closed-loop mechanism that triggers targeted pipeline reruns.

#### Feedback entry

- Record client's text feedback on the proposal
- Tag rejected directions (auto-avoid next time)
- Tag approved directions (prioritize next time)
- All feedback persists in that client's Brand Library, influencing all future projects

#### Targeted rerun (Checkpoint Node 5)

Based on feedback type, the system determines which node to rerun from. No need to restart from scratch:

| Feedback type | Example | Rerun from | Cost |
|--------------|---------|-----------|------|
| Overall direction wrong | "Strategy is off, Big Idea doesn't fit the brand" | Strategy (user chooses whether to also refresh Research) | High |
| Partial content dissatisfaction | "Competitor analysis too shallow", "Copy tone too formal" | Only the affected slide(s) | Low |
| Structure issue | "Don't need KOL page, add a crisis PR page" | Orchestrator re-plans structure | Medium |
| Resource mismatch | "These KOLs don't fit, use vertical niche bloggers" | Only Resource Agent | Low |

**Design principle**: The system suggests a rerun node based on feedback type. The user confirms before execution. This prevents full-pipeline reruns for minor issues.

---

## 3. User Journey

```
Account logs in (belongs to an Agency)
    ↓
Select or create client (shared across org)
    ↓
Upload files (Brand Library or Project Library)
    ↓
Input brief (natural language)
    ↓
Brief Analyzer processes
    ├── Insufficient info → ask follow-ups → user supplements → continue
    └── Sufficient →
              ↓
    [Node 1: User confirms brief interpretation]
    User reviews structured brief, can edit before proceeding
              ↓
    ┌──────────────────────────────────────────┐
    │              Parallel execution            │
    ├── Research Agent (competitor research)     │
    ├── Strategy Phase 1 (audience insights)    │
    └──────────────────────────────────────────┘
              ↓ Both complete, then merge
    Strategy Phase 2 (full strategy using research results)
              ↓
    Brand consistency check
              ↓
    [Node 2: User confirms strategy] ← most critical checkpoint
    Shows research data with timestamp + [Refresh] button
    Rerun options: strategy only / refresh research + strategy
              ↓
    Resource Agent (optional)
    ├── Social → KOL/KOC matching
    ├── PR → media resource matching
    ├── Offline → vendor matching
    ├── Ads → placement matching
    └── None needed → skip
              ↓
    Deck Orchestrator (generates slide structure)
              ↓
    [Node 3: User confirms/adjusts slide structure]
    Can add/remove/reorder, apply client-level or project-level templates
              ↓
    Slide Content Agent (generates per-slide)
              ║
              ║ After generation completes, triggers both:
              ╠══════════════════════╗
              ↓                      ↓
    Node 4 Gallery ready     Narrative Agent (background check)
                                     ↓
                           Suggestions pushed to Node 4
              ↓
    [Node 4: Gallery Review]
    Streaming display, browse as slides complete
    ├── Left: slide thumbnail nav (check/warning/blank)
    ├── Right: current slide preview + Narrative suggestions
    └── Bottom: progress + action buttons
              ↓
    User marks slides for revision
    ├── Has marks → batch regenerate flagged slides → return to Gallery
    └── No marks → confirm all
              ↓
    User confirms
              ↓
    PPT Builder → web preview (non-blocking) + download .pptx
              ↓
    Version saved
              ↓
    [Node 5: Client feedback entry]
    ├── Persists to Brand Library (influences future projects)
    └── Triggers targeted rerun (user selects rerun node)
```

---

## 4. Tech Stack Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent orchestration | LangGraph | State management, conditional branching, HITL |
| RAG | Pinecone + BGE-M3 | Brand style retrieval, historical reference (BGE-M3 for multilingual marketing terminology) |
| File processing | PyPDF2, python-pptx | Document parsing and PPT generation |
| Web search | Tavily | Research Agent real-time search |
| Backend | FastAPI | API layer |
| Async tasks | Celery + Redis | Heavy tasks (PPT generation, file vectorization) |
| Database | MongoDB | Client records, projects, versions, feedback |
| Frontend | Next.js | User interface |

---

## 5. Development Phases

### Phase 1: Core Pipeline (MVP)

- Brief Analyzer
- Research Agent basic (web search + internal history retrieval)
- Strategy Agent (Phase 1 insights + Phase 2 strategy, depends on Research)
- Deck System (Orchestrator + Slide Content Agent + Narrative Agent + PPT Builder)
- Human-in-the-loop Nodes 1-4 (brief, strategy, structure, Gallery Review)
- Three-tier deck structure priority (global / client / project)
- Basic RAG (text files)
- Resource Agent framework + KOL/KOC database (manual entry)

### Phase 2: Research and Resource Enhancement

- Research Agent enhancement: multimodal competitor analysis, third-party data platform integration
- Resource Agent expansion: media, vendor, and placement databases
- Human-in-the-loop Node 5 (client feedback + targeted rerun)
- Visual reference file processing (multimodal)
- KOL database third-party API integration (locale-specific: Chanmama/Feigua for China, CreatorIQ for global)

### Phase 3: Production Hardening

- Version management
- Client feedback closed loop
- CI/CD + monitoring
- Terraform deployment

---

## 6. Open Questions

- [ ] Processing depth for visual reference files (moodboard, competitor screenshots)
- [ ] Compliance and feasibility of social media data acquisition (varies by locale)
- [ ] Cold-start strategy for resource databases (where does initial data come from)
- [ ] Resource Agent trigger boundary: is Strategy output sufficient to determine resource types, or should the user explicitly select at Node 2?
- [ ] Narrative Agent prompt design: how to ensure suggestions are specific, actionable, and reference page numbers
- [x] ~~Node 4 per-slide interaction model~~ → Gallery Review with batch mark and regenerate
- [ ] Client feedback rerun: system auto-detects rerun node vs user manually selects
- [x] ~~Multilingual support priority~~ → Language Router: language detection + prompt template switching (Chinese / English). LLM stays Claude, embedding stays BGE-M3 (natively multilingual)
- [ ] Initial PPT template count and project type coverage
