"""Research Agent: web search + competitor visual analysis with caching and fallback."""
import json
import time

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm_structured
from backend.core.agents.schemas import ResearchResult
from backend.core.config import settings
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language
from backend.core.rag.cache import SemanticCache
from backend.core.stability.fallback import FallbackChain

SYSTEM_PROMPT = {
    "zh": "你是资深市场研究员。基于brief信息和网络调研，整合出有用的竞品和市场洞察。",
    "en": "You are a senior market researcher. Based on the brief and web research, synthesize competitor and market insights.",
}

cache = SemanticCache()


async def _search_tavily(query: str) -> list[dict]:
    from tavily import AsyncTavilyClient

    client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    response = await client.search(query, max_results=5)
    return [{"title": r["title"], "content": r["content"], "url": r["url"]} for r in response["results"]]


async def _search_duckduckgo(query: str) -> list[dict]:
    from duckduckgo_search import AsyncDDGS

    async with AsyncDDGS() as ddgs:
        results = await ddgs.atext(query, max_results=5)
    return [{"title": r["title"], "content": r["body"], "url": r["href"]} for r in results]



async def run_research(
    brief: dict,
    client_id: str,
    project_id: str | None = None,
    force_refresh: bool = False,
    budget: RequestBudget | None = None,
    competitor_screenshots: list[tuple[bytes, str]] | None = None,
) -> dict:
    client_name = brief.get("client_name", "")
    theme = brief.get("theme", "")
    search_query = f"{client_name} {theme} marketing campaign competitor"
    lang = detect_language(search_query)

    if not force_refresh:
        cached = await cache.get(client_id, search_query[:50])
        if cached:
            cached["from_cache"] = True
            return cached

    if budget:
        budget.use_search_call()

    # 1. Web search (with fallback chain)
    web_chain = FallbackChain(service_name="web_search")
    web_results, _ = await web_chain.execute(
        primary_fn=lambda: _search_tavily(search_query),
        secondary_fn=lambda: _search_duckduckgo(search_query),
        fallback_fn=lambda: [],
    )
    web_results = web_results or []

    # 2. Visual competitor analysis (if screenshots provided)
    visual_context = ""
    if competitor_screenshots:
        from backend.core.agents.visual_analysis import analyze_competitor_batch
        visual_analyses = await analyze_competitor_batch(competitor_screenshots, lang, budget)
        visual_context = "\n\n".join([json.dumps(v, ensure_ascii=False) for v in visual_analyses])

    web_context = "\n\n".join(
        [f"[{r['title']}] {r['content']}" for r in web_results]
    )

    user_msg = f"""Brief: {json.dumps(brief, ensure_ascii=False)}

Web research results:
{web_context}

Visual competitor analysis:
{visual_context or "No visual analysis available."}"""

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

    await cache.set(client_id, search_query[:50], result)
    return result
