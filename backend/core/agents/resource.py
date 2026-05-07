"""Resource Agent: KOL/KOC matching based on strategy output."""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm, strip_code_block
from backend.core.config import settings
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language
from backend.core.rag.retriever import retrieve

SYSTEM_PROMPT = {
    "zh": """你是资深媒介策划。基于策略方向和KOL数据库检索结果，推荐最适合的KOL/KOC资源组合。

输出JSON格式：
{
  "recommended_resources": [
    {"name": "名称", "type": "kol/koc", "reason": "推荐理由", "estimated_cost": "预估费用", "tags": ["标签"]}
  ],
  "channel_allocation": {"channel": "比例或预算"}
}""",

    "en": """You are a senior media planner. Based on the strategy direction and KOL database search results, recommend the most suitable KOL/KOC resource mix.

Output in JSON format:
{
  "recommended_resources": [
    {"name": "name", "type": "kol/koc", "reason": "recommendation rationale", "estimated_cost": "estimated cost", "tags": ["tags"]}
  ],
  "channel_allocation": {"channel": "percentage or budget"}
}""",
}

SOCIAL_RESOURCE_TYPES = {"kol", "koc", "influencer", "红人", "达人"}
SOCIAL_CHANNELS = {"小红书", "抖音", "weibo", "instagram", "tiktok", "youtube", "bilibili", "douyin"}


def _needs_resources(strategy: dict) -> bool:
    """Check if strategy explicitly includes social/influencer resource types or channels."""
    resource_types = [t.lower() for t in strategy.get("resource_types", [])]
    if any(t in SOCIAL_RESOURCE_TYPES for t in resource_types):
        return True

    channels = [c.get("name", "").lower() if isinstance(c, dict) else str(c).lower() for c in strategy.get("channels", [])]
    if any(ch in SOCIAL_CHANNELS for ch in channels):
        return True

    # Fallback: keyword scan for backwards compatibility with unstructured strategy
    text = json.dumps(strategy, ensure_ascii=False).lower()
    return any(ch in text for ch in SOCIAL_RESOURCE_TYPES | SOCIAL_CHANNELS)


async def run_resource_agent(
    strategy: dict,
    client_id: str,
    budget: RequestBudget | None = None,
) -> dict:
    if not _needs_resources(strategy):
        return {"skipped": True, "reason": "No social/influencer channels in strategy"}

    lang = detect_language(json.dumps(strategy, ensure_ascii=False))
    strategy_text = json.dumps(strategy, ensure_ascii=False)[:2000]

    # Build targeted search query from structured fields
    channels = [c.get("name", "") if isinstance(c, dict) else str(c) for c in strategy.get("channels", [])]
    search_query = f"{strategy.get('big_idea', '')} {' '.join(channels)} {' '.join(strategy.get('resource_types', []))}"
    search_query = search_query.strip() or strategy_text[:500]

    kol_results = await retrieve(
        query=search_query,
        namespaces=[f"resource_kol_{client_id}"],
        top_k=10,
        score_threshold=0.3,
    )

    kol_context = "\n".join([r.text for r in kol_results]) if kol_results else "No KOL data available in database."

    user_msg = f"Strategy: {strategy_text}\n\nKOL database results:\n{kol_context}"
    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=user_msg),
    ]

    text = await invoke_llm(messages, budget=budget, temperature=0.2, max_tokens=2048)
    text = strip_code_block(text)

    return json.loads(text)
