"""Media Planning Agent: transforms strategy output into a structured tier-level media matrix.

Sits between Strategy P2 (confirmed) and Resource Agent in the pipeline.
Strategy P2 owns channel-level budget; this agent owns tier-level breakdown.
"""
from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm_structured
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import resolve_output_language
from backend.core.models.media_plan import MediaPlan
from backend.core.rag.campaign_retriever import format_campaign_context, retrieve_campaign_knowledge

SYSTEM_PROMPT = {
    "zh": """你是资深媒介策划专家。你的任务是将策略方向转化为可执行的媒介资源矩阵。

你需要完成三步：
1. 策略解读：将策略语言翻译成媒介需求（什么样的创作者/媒体能表达这个策略）
2. 矩阵设计：在每个渠道内部定义层级结构（头部/腰部/KOC/媒体），指定每层的角色和数量
3. 预算拆分：将每个渠道的预算进一步拆分到各层级，给出百分比

核心原则：
- 头部（top）：制造话题声量、创造内容事件
- 腰部（mid）：放大传播、多角度诠释
- KOC/尾部（koc/tail）：真实UGC、口碑渗透、提升搜索SEO
- 媒体（media）：公信力背书、行业声量

你的 selection_criteria 字段会直接用于后续资源检索，请写得具体可查询：
- 好的：粉丝50万+美妆垂类、内容风格偏生活化、近3个月有品牌合作
- 差的：优质达人、合适的KOL

如有历史参考案例，请参考但不照搬——每个项目有独特约束。""",

    "en": """You are a senior media planning specialist. Your task is to transform strategy direction into an actionable media resource matrix.

Three steps:
1. Strategy interpretation: translate strategy language into media requirements (what type of creators/media can express this strategy)
2. Matrix design: define tier structure within each channel (top/mid/koc/media), specifying role and count per tier
3. Budget allocation: break down each channel's budget into tier-level percentages

Core principles:
- Top tier: create topic buzz, produce content events
- Mid tier: amplify reach, multi-angle interpretation
- KOC/tail: authentic UGC, word-of-mouth, search SEO
- Media: credibility endorsement, industry presence

Your selection_criteria field drives downstream resource retrieval — be specific and queryable:
- Good: "500K+ followers beauty vertical, lifestyle content style, brand collaborations in past 3 months"
- Bad: "quality creators", "suitable KOLs"

If historical references are provided, use them as guidance but don't copy blindly — each project has unique constraints.""",
}


async def run_media_planner(
    big_idea: str,
    channels: list[dict],
    budget_allocation: dict,
    audience_insight: str = "",
    content_tone: str = "",
    kpis: list[str] | None = None,
    budget: RequestBudget | None = None,
    output_language: str = "auto",
    org_id: str | None = None,
) -> MediaPlan:
    """Generate a structured media plan from strategy output.

    Args:
        big_idea: Strategy P2's big idea
        channels: Strategy P2's channel list (name, role, etc.)
        budget_allocation: Strategy P2's channel-level budget split (channel -> percentage/amount)
        audience_insight: Target audience description
        content_tone: Content tone direction
        kpis: Key performance indicators
        budget: Request budget tracker
        output_language: "zh" / "en" / "auto"
        org_id: Organization ID for campaign knowledge retrieval
    """
    lang = resolve_output_language(output_language, big_idea)

    campaign_context = ""
    if org_id:
        campaign_query = f"{big_idea} {content_tone} media plan tier allocation budget"
        campaign_results = await retrieve_campaign_knowledge(
            query=campaign_query,
            org_id=org_id,
            profile_name="media_planning",
        )
        campaign_context = format_campaign_context(campaign_results, max_records=3)

    channel_desc = _format_channels(channels, budget_allocation)

    user_msg = (
        f"Big Idea: {big_idea}\n"
        f"Content Tone: {content_tone or 'not specified'}\n"
        f"Target Audience: {audience_insight or 'not specified'}\n"
        f"KPIs: {', '.join(kpis) if kpis else 'not specified'}\n\n"
        f"Channel Budget Allocation (from Strategy):\n{channel_desc}\n\n"
        f"Please design the tier-level media matrix for each channel above."
    )

    if campaign_context:
        user_msg += (
            f"\n\nHistorical campaign references (similar projects, for context only):\n"
            f"{campaign_context}"
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT[lang]),
        HumanMessage(content=user_msg),
    ]

    result = await invoke_llm_structured(
        messages,
        output_schema=MediaPlan,
        budget=budget,
        temperature=0.3,
        max_tokens=3000,
    )

    _compute_absolute_budgets(result, budget_allocation)

    return result


def _format_channels(channels: list[dict], budget_allocation: dict) -> str:
    """Format channel + budget info for the prompt."""
    lines = []
    for ch in channels:
        name = ch.get("name", "") if isinstance(ch, dict) else str(ch)
        role = ch.get("role", "") if isinstance(ch, dict) else ""
        budget_share = budget_allocation.get(name, "unknown")
        line = f"- {name}: budget share = {budget_share}"
        if role:
            line += f", strategic role = {role}"
        lines.append(line)

    unmatched = set(budget_allocation.keys()) - {
        (ch.get("name", "") if isinstance(ch, dict) else str(ch)) for ch in channels
    }
    for name in sorted(unmatched):
        lines.append(f"- {name}: budget share = {budget_allocation[name]}")

    return "\n".join(lines) if lines else "No channel budget information available."


def _compute_absolute_budgets(plan: MediaPlan, budget_allocation: dict) -> None:
    """Fill in budget_absolute from channel budget and tier percentage.

    Only works if budget_allocation values are numeric. Gracefully skips otherwise.
    """
    for tier in plan.tiers:
        if tier.budget_absolute is not None:
            continue
        channel_budget = budget_allocation.get(tier.channel)
        if channel_budget is None:
            continue
        try:
            channel_amount = float(channel_budget)
            tier.budget_absolute = round(channel_amount * tier.budget_percentage / 100, 2)
        except (ValueError, TypeError):
            pass
