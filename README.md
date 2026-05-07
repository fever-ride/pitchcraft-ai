# Pitchcraft

AI-powered proposal automation for agency Account teams. Takes a client brief in, delivers a presentation-ready PowerPoint deck out. Uses a multi-agent pipeline with human checkpoints at every critical decision point.

## Problem

Account teams at PR/marketing agencies burn 3-5 days per pitch doing work that is largely repeatable: structuring decks, researching competitors, writing strategy frameworks, matching KOLs. Pitchcraft automates the repeatable parts so Account teams can focus on judgment and client relationships.

## How It Works

```
Brief → [Research ‖ Strategy P1] → Strategy P2 → Resources → Deck → PPT
```

Six agents run in a stateful LangGraph pipeline with five human-in-the-loop checkpoints:

1. **Brief Analyzer** parses natural language briefs, extracts structured fields, asks follow-ups for missing info.
2. **Research Agent** runs web search and internal history retrieval for competitor analysis. Runs in parallel with Strategy Phase 1.
3. **Strategy Agent** operates in two phases. Phase 1 (audience insights, brand direction) runs without competitor data. Phase 2 (Big Idea, channel mix, budget) integrates research results.
4. **Resource Agent** is pluggable. Matches KOLs, media outlets, vendors, or ad placements based on channel strategy. Skips entirely when not needed.
5. **Deck System** has four sub-agents. Orchestrator plans slide structure. Slide Content Agent generates per-page content. Narrative Agent runs in the background and provides coherence suggestions (non-blocking). PPT Builder assembles the final `.pptx`.

### Human Checkpoints

| Node | Decision |
|------|----------|
| 1 | Confirm brief interpretation |
| 2 | Confirm strategy direction. Can refresh research or rerun strategy. |
| 3 | Confirm or adjust slide structure |
| 4 | Gallery Review: browse all slides, mark pages for batch regeneration |
| 5 | Record client feedback, trigger targeted rerun from a specific node |

## Architecture

| Layer | Technology |
|-------|-----------|
| Agent orchestration | LangGraph (fan-out/fan-in, HITL pauses, conditional branches) |
| Backend | FastAPI + Celery + Redis |
| Frontend | Next.js 14 + TypeScript + WebSocket |
| RAG | Pinecone (namespace-isolated) + BGE-M3 (self-hosted) |
| Database | MongoDB Atlas (multi-tenant) |
| LLM | Claude Sonnet |
| PPT generation | python-pptx |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| BGE-M3 over text-embedding-3-small | Better Chinese PR/marketing terminology support. Open-source, self-hosted, no API cost. |
| Narrative Agent as non-blocking advisor | No flow control, no retry loops. Suggestions shown alongside content in Gallery view. |
| Research and Strategy Phase 1 in parallel | Fan-out/fan-in via LangGraph. Phase 2 waits for research. Saves ~8 seconds per run. |
| Token-based semantic chunking | Language-agnostic. Splits on paragraph/sentence boundaries, not character counts. |
| Soft-delete for files | Running pipelines unaffected when teammates delete shared Brand Library assets. |
| Research timestamp + user-controlled refresh | User decides whether to reuse cached research or refresh before strategy rerun. |

## Multi-Tenancy

```
Organization (Agency)
  └── Users (Accounts): account / lead_account / admin
       └── Clients (shared across org, Brand Library at this level)
            └── Projects (assignable to specific accounts)
                 └── Proposals (created by individual accounts)
```

## Project Structure

```
pitchcraft/
├── backend/
│   ├── api/                    # FastAPI endpoints + WebSocket
│   ├── core/
│   │   ├── agents/             # All agent implementations
│   │   ├── graph/              # LangGraph pipeline, state, nodes
│   │   ├── rag/                # Indexer, retriever, cache
│   │   ├── language/           # Language detection + prompt templates
│   │   ├── stability/          # Request budget + fallback chains
│   │   └── database/           # MongoDB repositories
│   └── tests/
├── frontend/
│   ├── app/                    # Next.js App Router
│   ├── components/
│   │   ├── gallery/            # Node 4 Gallery Review UI
│   │   ├── hitl/               # Human-in-the-loop UIs
│   │   └── pipeline/           # Pipeline execution view
│   └── hooks/                  # WebSocket hooks
└── infrastructure/
    └── docker/                 # Docker Compose (7 services)
```

## Getting Started

```bash
# Prerequisites: Docker, Node.js 18+, Python 3.11+
docker compose up -d

# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

## Documentation

- [PRD](./PRD.md) — Product requirements, user journey, feature specs
- [Architecture](./Architecture.md) — Technical design, data models, API specs
- [Roadmap](./ROADMAP.md) — Phased development plan

## License

Proprietary. All rights reserved.
