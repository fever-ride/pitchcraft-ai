"""Research Agent: web search + social data + internal history with caching and fallback."""
import json
import time

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm, strip_code_block
from backend.core.agents.social_data import SocialDataResult, fetch_social_data
from backend.core.config import settings
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language
from backend.core.rag.cache import SemanticCache
from backend.core.rag.retriever import retrieve_for_client
from backend.core.stability.fallback import FallbackChain

SYSTEM_PROMPT = {
    "zh": """你是资深市场研究员。基于brief信息、网络调研、社交数据和内部资料，整合出有用的竞品和市场洞察。

输出严格JSON格式：
{{
  "competitors": [
    {{
      "name": "竞品名",
      "positioning": "定位",
      "recent_activity": "近期动向",
      "social_presence": {{
        "platforms": ["活跃平台"],
        "content_style": "内容风格描述",
        "engagement_level": "high/medium/low",
        "notable_campaigns": ["近期campaign"]
      }}
    }}
  ],
  "market_trends": ["趋势描述"],
  "content_trends": [
    {{"trend": "趋势名", "platforms": ["平台"], "relevance": "与brief的关联"}}
  ],
  "opportunities": ["机会点"],
  "risks": ["需注意的风险"],
  "internal_references": ["相关历史项目摘要"],
  "recommended_approach": "基于以上分析的策略建议（1-2句）"
}}""",

    "en": """You are a senior market researcher. Based on the brief, web research, social data, and internal materials, synthesize competitor and market insights.

Output strictly in JSON format:
{{
  "competitors": [
    {{
      "name": "competitor",
      "positioning": "positioning",
      "recent_activity": "recent moves",
      "social_presence": {{
        "platforms": ["active platforms"],
        "content_style": "content style description",
        "engagement_level": "high/medium/low",
        "notable_campaigns": ["recent campaigns"]
      }}
    }}
  ],
  "market_trends": ["trend descriptions"],
  "content_trends": [
    {{"trend": "trend name", "platforms": ["platforms"], "relevance": "relevance to brief"}}
  ],
  "opportunities": ["opportunity areas"],
  "risks": ["risks to be aware of"],
  "internal_references": ["relevant past project summaries"],
  "recommended_approach": "strategic recommendation based on above (1-2 sentences)"
}}""",
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


def _detect_locale(brief: dict) -> str:
    """Infer locale from brief content for social data source selection."""
    text = json.dumps(brief, ensure_ascii=False).lower()
    cn_signals = {"中国", "中文", "国内", "小红书", "抖音", "微博", "微信", "bilibili", "天猫", "京东"}
    if any(s in text for s in cn_signals):
        return "cn"
    return "global"


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
    locale = _detect_locale(brief)

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
        fallback_fn=lambda: _search_internal_only(search_query, client_id, project_id),
    )
    web_results = web_results or []

    # 2. Social data (locale-aware)
    social_results: list[SocialDataResult] = []
    social_query = f"{client_name} {theme}"
    if social_query.strip():
        social_results = await fetch_social_data(social_query, locale=locale)

    social_context = "\n".join([r.to_text() for r in social_results]) if social_results else ""

    # 3. Internal RAG
    rag_results = await retrieve_for_client(
        search_query, client_id, project_id, top_k=5
    )
    internal_context = "\n".join([r.text for r in rag_results])

    # 4. Visual competitor analysis (if screenshots provided)
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

Social media data:
{social_context or "No social data available."}

Visual competitor analysis:
{visual_context or "No visual analysis available."}

Internal project history:
{internal_context}"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=user_msg),
    ]

    text = await invoke_llm(messages, budget=budget, temperature=0, max_tokens=4000)
    text = strip_code_block(text)

    result = json.loads(text)
    result["fetched_at"] = time.time()
    result["from_cache"] = False
    result["social_data_source"] = locale
    result["has_visual_analysis"] = bool(competitor_screenshots)

    await cache.set(client_id, search_query[:50], result)
    return result
