"""Resource Agent: multi-type resource matching based on structured strategy output."""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm, strip_code_block
from backend.core.config import settings
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language
from backend.core.models.resource import resource_namespace
from backend.core.rag.retriever import retrieve

SYSTEM_PROMPT = {
    "zh": """你是资深媒介策划。基于策略方向和资源库检索结果，推荐最适合的资源组合。

可用资源类型：KOL/KOC（社交达人）、Media（媒体）、Vendor（供应商）、Placement（广告位）

输出JSON格式：
{{
  "recommended_resources": [
    {{"name": "名称", "type": "kol/koc/media/vendor/placement", "reason": "推荐理由", "estimated_cost": "预估费用", "tags": ["标签"]}}
  ],
  "channel_allocation": {{"渠道": "比例或预算"}},
  "missing_resources": ["库中未找到但建议补充的资源类型或方向"]
}}""",

    "en": """You are a senior media planner. Based on the strategy direction and resource database results, recommend the most suitable resource mix.

Available resource types: KOL/KOC (social influencers), Media (outlets/journalists), Vendor (event/production companies), Placement (ad inventory)

Output in JSON format:
{{
  "recommended_resources": [
    {{"name": "name", "type": "kol/koc/media/vendor/placement", "reason": "recommendation rationale", "estimated_cost": "estimated cost", "tags": ["tags"]}}
  ],
  "channel_allocation": {{"channel": "percentage or budget"}},
  "missing_resources": ["resource types or directions not found in DB but recommended to add"]
}}""",
}

# --- Trigger logic: which resource types does a strategy need? ---

SOCIAL_RESOURCE_TYPES = {"kol", "koc", "influencer", "红人", "达人"}
SOCIAL_CHANNELS = {"小红书", "抖音", "weibo", "instagram", "tiktok", "youtube", "bilibili", "douyin"}
PR_KEYWORDS = {"pr", "media relations", "媒体", "公关", "press", "记者", "发稿", "媒介"}
VENDOR_KEYWORDS = {"event", "活动", "线下", "场地", "拍摄", "制作", "production", "photography", "venue"}
PLACEMENT_KEYWORDS = {"ooh", "户外", "电梯", "cinema", "magazine", "广告位", "投放", "placement", "billboard"}


def _detect_needed_types(strategy: dict) -> list[str]:
    """Determine which resource types a strategy needs. Returns list like ['kol', 'media', 'placement']."""
    needed = []
    resource_types = [t.lower() for t in strategy.get("resource_types", [])]
    channels = [c.get("name", "").lower() if isinstance(c, dict) else str(c).lower() for c in strategy.get("channels", [])]
    text = json.dumps(strategy, ensure_ascii=False).lower()

    # KOL/KOC
    if any(t in SOCIAL_RESOURCE_TYPES for t in resource_types):
        needed.append("kol")
    elif any(ch in SOCIAL_CHANNELS for ch in channels):
        needed.append("kol")
    elif any(kw in text for kw in SOCIAL_RESOURCE_TYPES | SOCIAL_CHANNELS):
        needed.append("kol")

    # Media
    if "media" in resource_types:
        needed.append("media")
    elif any(kw in text for kw in PR_KEYWORDS):
        needed.append("media")

    # Vendor
    if "vendor" in resource_types or "event" in resource_types:
        needed.append("vendor")
    elif any(kw in text for kw in VENDOR_KEYWORDS):
        needed.append("vendor")

    # Placement
    if "placement" in resource_types:
        needed.append("placement")
    elif any(kw in text for kw in PLACEMENT_KEYWORDS):
        needed.append("placement")

    return needed


def _needs_resources(strategy: dict) -> bool:
    """Check if strategy requires any resource type."""
    return len(_detect_needed_types(strategy)) > 0


async def run_resource_agent(
    strategy: dict,
    client_id: str,
    budget: RequestBudget | None = None,
) -> dict:
    needed_types = _detect_needed_types(strategy)
    if not needed_types:
        return {"skipped": True, "reason": "No resource-requiring channels in strategy"}

    lang = detect_language(json.dumps(strategy, ensure_ascii=False))
    strategy_text = json.dumps(strategy, ensure_ascii=False)[:2000]

    # Build search query from structured fields
    channels = [c.get("name", "") if isinstance(c, dict) else str(c) for c in strategy.get("channels", [])]
    search_query = f"{strategy.get('big_idea', '')} {' '.join(channels)} {' '.join(strategy.get('resource_types', []))}"
    search_query = search_query.strip() or strategy_text[:500]

    # Retrieve from all needed namespaces
    all_results = []
    for rtype in needed_types:
        ns = resource_namespace(rtype, client_id)
        results = await retrieve(
            query=search_query,
            namespaces=[ns],
            top_k=8,
            score_threshold=0.3,
        )
        if results:
            all_results.extend(results)

    resource_context = "\n".join([r.text for r in all_results]) if all_results else "No resources found in database."

    user_msg = (
        f"Strategy:\n{strategy_text}\n\n"
        f"Required resource types: {', '.join(needed_types)}\n\n"
        f"Resource database results:\n{resource_context}"
    )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=user_msg),
    ]

    text = await invoke_llm(messages, budget=budget, temperature=0.2, max_tokens=2048)
    text = strip_code_block(text)

    result = json.loads(text)
    result["triggered_types"] = needed_types
    return result
