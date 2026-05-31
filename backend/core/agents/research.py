"""Research Agent: multi-dimensional web search + competitor analysis.

Results are persisted to MongoDB (research_results collection) keyed by
(client_id, brief_hash). On a new pipeline run, if an identical brief was
researched within the last 30 days, the stored result is reused automatically
unless force_refresh=True.

The Redis SemanticCache previously used here was removed — it had a buggy
date_bucket TTL mechanism and was solving a persistence problem with the wrong
tool.
"""
import asyncio
import hashlib
import json
import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm_structured
from backend.core.agents.schemas import ResearchResult
from backend.core.config import settings
from backend.core.database.connection import get_database
from backend.core.database.repositories.research_results import ResearchResultRepository
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language
from backend.core.stability.fallback import FallbackChain

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = {
    "zh": (
        "你是资深市场研究员。基于brief信息和网络调研，从六个维度分析竞品和市场：\n"
        "1. 品牌定位(positioning) 2. 目标受众(target_audience) 3. 核心主张(key_message)\n"
        "4. 近期动态(recent_activity) 5. 渠道表现(social_presence) 6. 优劣势(strengths/weaknesses)\n"
        "整合出有实质参考价值的洞察，不要泛泛而谈。"
    ),
    "en": (
        "You are a senior market researcher. Analyze competitors and the market across six dimensions: "
        "positioning, target audience, key message/creative direction, recent activities, "
        "channel presence, and strengths/weaknesses. "
        "Synthesize actionable insights from the brief and web research — avoid generic observations."
    ),
}


async def _search_tavily(query: str, max_results: int = 5) -> list[dict]:
    from tavily import AsyncTavilyClient

    client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    response = await client.search(query, max_results=max_results)
    return [{"title": r["title"], "content": r["content"], "url": r["url"]} for r in response["results"]]


async def _search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    from duckduckgo_search import AsyncDDGS

    async with AsyncDDGS() as ddgs:
        results = await ddgs.atext(query, max_results=max_results)
    return [{"title": r["title"], "content": r["body"], "url": r["href"]} for r in results]


async def _run_single_search(query: str) -> list[dict]:
    """Run one search query through Tavily → DDG fallback chain."""
    chain = FallbackChain(service_name="web_search")
    results, _ = await chain.execute(
        primary_fn=lambda: _search_tavily(query, max_results=5),
        secondary_fn=lambda: _search_duckduckgo(query, max_results=5),
        fallback_fn=lambda: [],
    )
    return results or []


def _build_search_queries(brief: dict, competitor_names: list[str]) -> list[str]:
    """Build three targeted search queries covering different research dimensions."""
    def _v(s: str) -> str:
        return "" if (not s or s == "not provided") else s

    client_name = _v(brief.get("client_name", ""))
    category = _v(brief.get("category", ""))
    theme = _v(brief.get("theme", ""))
    audience = _v(brief.get("audience", ""))

    queries: list[str] = []

    # Q1 — Competitive landscape
    if client_name:
        queries.append(f"{client_name} {category} competitor brand positioning marketing strategy")
    else:
        queries.append(f"{category} competitor brand analysis market landscape")

    # Q2 — Industry & consumer trends
    trend_seeds = " ".join(filter(None, [category, audience]))
    queries.append(f"{trend_seeds} market trend consumer insight 2025")

    # Q3 — Named competitors (from brief) or theme/category best practice
    if competitor_names:
        comp_str = " ".join(competitor_names[:3])
        queries.append(f"{comp_str} brand campaign marketing strategy")
    else:
        theme_seed = theme or category
        queries.append(f"{theme_seed} marketing campaign case study best practice")

    return queries


def _merge_web_results(all_results: list[list[dict]], max_total: int = 15) -> list[dict]:
    """Deduplicate by URL and cap total results."""
    seen_urls: set[str] = set()
    merged: list[dict] = []
    for batch in all_results:
        for r in batch:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                merged.append(r)
                if len(merged) >= max_total:
                    return merged
    return merged


def _compute_brief_hash(brief: dict) -> str:
    """Stable SHA-256 hash of brief content for persistent result lookup."""
    serialized = json.dumps(brief, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


def format_research_for_prompt(research: dict) -> str:
    """Compact structured summary for injection into strategy prompts.

    Replaces the raw JSON[:3000] truncation with a prioritised text block
    that fits in ~600 tokens regardless of how many competitors were found.
    """
    lines: list[str] = []

    competitors = research.get("competitors", [])
    if competitors:
        lines.append("Competitors:")
        for c in competitors[:4]:
            if not isinstance(c, dict):
                continue
            name = c.get("name", "")
            parts = [p for p in [
                c.get("positioning"),
                f"audience: {c.get('target_audience')}" if c.get("target_audience") else None,
                f"message: {c.get('key_message')}" if c.get("key_message") else None,
                f"recent: {c.get('recent_activity')}" if c.get("recent_activity") else None,
            ] if p]
            detail = " | ".join(parts) if parts else "no detail"
            lines.append(f"  - {name}: {detail}")
            strengths = c.get("strengths", [])
            weaknesses = c.get("weaknesses", [])
            if strengths:
                lines.append(f"    ↑ {', '.join(strengths[:2])}")
            if weaknesses:
                lines.append(f"    ↓ {', '.join(weaknesses[:2])}")

    trends = research.get("market_trends", [])
    if trends:
        lines.append("Market Trends:")
        for t in trends[:4]:
            lines.append(f"  - {t}")

    content_trends = research.get("content_trends", [])
    if content_trends:
        lines.append("Content Trends:")
        for ct in content_trends[:3]:
            if isinstance(ct, dict):
                trend = ct.get("trend", "")
                platforms = ct.get("platforms", [])
                platform_str = f" [{', '.join(platforms)}]" if platforms else ""
                lines.append(f"  - {trend}{platform_str}")

    opps = research.get("opportunities", [])
    if opps:
        lines.append("Opportunities:")
        for o in opps[:3]:
            lines.append(f"  - {o}")

    risks = research.get("risks", [])
    if risks:
        lines.append("Risks:")
        for r in risks[:2]:
            lines.append(f"  - {r}")

    approach = research.get("recommended_approach", "")
    if approach:
        lines.append(f"Recommended Approach: {approach}")

    return "\n".join(lines) if lines else "(no research data)"


async def run_research(
    brief: dict,
    client_id: str,
    org_id: str | None = None,
    project_id: str | None = None,
    force_refresh: bool = False,
    budget: RequestBudget | None = None,
    competitor_names: list[str] | None = None,
    competitor_screenshots: list[tuple[bytes, str]] | None = None,
) -> dict:
    """Run multi-dimensional research with MongoDB-backed result persistence.

    On each call:
    1. Compute brief_hash from the structured brief content.
    2. If force_refresh=False, check MongoDB for a matching result within 30 days.
       If found, return it immediately (from_cache=True).
    3. Otherwise run 3 parallel web searches, synthesize via LLM, save to MongoDB.

    Args:
        brief: structured brief dict (StructuredBrief.model_dump())
        client_id: for result scoping and lookup
        org_id: stored with result for future org-level queries
        project_id: unused, kept for signature stability
        force_refresh: bypass stored result and re-run searches
        budget: request budget tracker
        competitor_names: from StructuredBrief.competitors, used for Q3 targeted search
        competitor_screenshots: optional AE-uploaded screenshots for visual analysis
    """
    queries = _build_search_queries(brief, competitor_names or [])
    lang = detect_language(" ".join(queries))
    brief_hash = _compute_brief_hash(brief)

    # --- Check MongoDB for a recent matching result ---
    if not force_refresh:
        try:
            db = await get_database()
            repo = ResearchResultRepository(db)
            existing = await repo.find_recent(client_id, brief_hash, max_age_days=30)
            if existing:
                result = existing["result"]
                result["from_cache"] = True
                result["cached_at"] = existing.get("created_at")
                logger.info(f"Research result reused from MongoDB for client {client_id}")
                return result
        except Exception as e:
            logger.warning(f"MongoDB research lookup failed, proceeding with fresh search: {e}")

    # --- Run 3 parallel web searches ---
    if budget:
        for _ in queries:
            budget.use_search_call()

    search_tasks = [_run_single_search(q) for q in queries]
    all_results = await asyncio.gather(*search_tasks, return_exceptions=True)
    clean_results = [r if isinstance(r, list) else [] for r in all_results]
    web_results = _merge_web_results(clean_results, max_total=15)

    # --- Optional visual competitor analysis ---
    visual_context = ""
    if competitor_screenshots:
        from backend.core.agents.visual_analysis import analyze_competitor_batch
        visual_analyses = await analyze_competitor_batch(competitor_screenshots, lang, budget)
        visual_context = "\n\n".join([json.dumps(v, ensure_ascii=False) for v in visual_analyses])

    web_context = "\n\n".join(
        [f"[{r['title']}] {r['content']}" for r in web_results]
    )

    user_msg = f"""Brief: {json.dumps(brief, ensure_ascii=False)}

Web research results (across {len(queries)} targeted queries):
{web_context}

Visual competitor analysis:
{visual_context or "Not available."}"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=user_msg),
    ]

    structured = await invoke_llm_structured(
        messages, output_schema=ResearchResult, budget=budget, temperature=0, max_tokens=4000
    )

    result = structured.model_dump()
    result["fetched_at"] = time.time()
    result["from_cache"] = False
    result["has_visual_analysis"] = bool(competitor_screenshots)

    # --- Persist to MongoDB ---
    try:
        db = await get_database()
        repo = ResearchResultRepository(db)
        await repo.save_result(
            client_id=client_id,
            org_id=org_id or "",
            brief_hash=brief_hash,
            result=result,
            queries_used=queries,
        )
    except Exception as e:
        logger.warning(f"Failed to persist research result: {e}")

    return result
