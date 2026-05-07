"""Research Agent: web search + internal history search with caching and fallback."""
import json
import time

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm, strip_code_block
from backend.core.config import settings
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language
from backend.core.rag.cache import SemanticCache
from backend.core.rag.retriever import retrieve_for_client
from backend.core.stability.fallback import FallbackChain

SYSTEM_PROMPT = {
    "zh": """你是资深市场研究员。基于brief信息和调研素材，整合出有用的竞品和市场洞察。

输出JSON格式：
{
  "competitors": [{"name": "竞品名", "positioning": "定位", "recent_activity": "近期动向"}],
  "market_trends": ["趋势描述"],
  "opportunities": ["机会点"],
  "internal_references": ["相关历史项目摘要"]
}""",

    "en": """You are a senior market researcher. Based on the brief and research materials, synthesize competitor and market insights.

Output in JSON format:
{
  "competitors": [{"name": "competitor", "positioning": "positioning", "recent_activity": "recent moves"}],
  "market_trends": ["trend descriptions"],
  "opportunities": ["opportunity areas"],
  "internal_references": ["relevant past project summaries"]
}""",
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


async def _search_internal_only(query: str, client_id: str, project_id: str | None) -> list[dict]:
    rag_results = await retrieve_for_client(query, client_id, project_id, top_k=5)
    return [{"title": "Internal", "content": r.text, "url": ""} for r in rag_results]


async def run_research(
    brief: dict,
    client_id: str,
    project_id: str | None = None,
    force_refresh: bool = False,
    budget: RequestBudget | None = None,
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

    web_chain = FallbackChain(service_name="web_search")
    web_results, _ = await web_chain.execute(
        primary_fn=lambda: _search_tavily(search_query),
        secondary_fn=lambda: _search_duckduckgo(search_query),
        fallback_fn=lambda: _search_internal_only(search_query, client_id, project_id),
    )
    web_results = web_results or []

    rag_results = await retrieve_for_client(
        search_query, client_id, project_id, top_k=5
    )
    internal_context = "\n".join([r.text for r in rag_results])

    web_context = "\n\n".join(
        [f"[{r['title']}] {r['content']}" for r in web_results]
    )

    user_msg = f"""Brief: {brief}

Web research results:
{web_context}

Internal project history:
{internal_context}"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=user_msg),
    ]

    text = await invoke_llm(messages, budget=budget, temperature=0, max_tokens=3000)
    text = strip_code_block(text)

    result = json.loads(text)
    result["fetched_at"] = time.time()
    result["from_cache"] = False

    await cache.set(client_id, search_query[:50], result)
    return result
