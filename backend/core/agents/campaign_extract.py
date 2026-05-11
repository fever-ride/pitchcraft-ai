"""Campaign Knowledge Base extraction: 3 parallel LLM calls → merged CampaignRecord."""
import asyncio
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm_structured
from backend.core.language.detector import detect_language
from backend.core.models.campaign_record import (
    CampaignRecord,
    Confidence,
    ConfirmationStatus,
    ExtractionBackground,
    ExtractionExecution,
    ExtractionOutcome,
)

logger = logging.getLogger(__name__)

# --- Prompts ---

BACKGROUND_PROMPT = {
    "zh": """你是资深campaign分析师。从结案报告中提取【项目背景+策略+传播规划+deck结构】信息。

提取规则：
1. 只提取报告中明确提到的信息，不要推测
2. meta字段用于检索匹配，尽量填完整
3. strategy_decisions关注"选了什么方向、为什么"
4. communication_plan关注"怎么打"：渠道角色分配、内容方向、传播节奏
5. channel_mix中每个渠道应有明确的角色定义（引爆/种草/转化/沉淀等），并标注channel_type（social/offline/pr/paid）
6. phasing_structure是传播阶段模式（如"三阶段：预热/引爆/长尾"），phasing_rhythm是节奏逻辑（如"首波引爆后5-7天跟进第二波"）
7. deck_info如果报告提到了提报结构就填

注意区分：
- communication_plan是策略层（渠道怎么配合），不是执行层（具体买了什么）
- rejected_directions每条必须包含direction（方向名称），reason可选（放弃原因）
- 只记录报告中明确提到"曾考虑但放弃"的方向""",
    "en": """You are a senior campaign analyst. Extract [project background + strategy + communication plan + deck structure] from this recap report.

Rules:
1. Only extract explicitly stated information — do not speculate
2. Fill meta fields as completely as possible (used for retrieval matching)
3. strategy_decisions: focus on "what direction was chosen and why"
4. communication_plan: focus on "how to fight" — channel roles, content direction, phasing
5. Each channel in channel_mix should have a clear role (ignite/seed/convert/sustain) and a channel_type (social/offline/pr/paid)
6. phasing_structure = phase pattern (e.g. "three phases: teaser/launch/sustain"), phasing_rhythm = tempo logic (e.g. "second wave 5-7 days after initial burst")
7. Fill deck_info only if the report mentions presentation structure

Key distinctions:
- communication_plan is strategic (how channels work together), NOT tactical (what was bought)
- rejected_directions: each entry must have a direction (name), reason is optional (why it was dropped)
- Only record directions the report explicitly says were considered and dropped""",
}

EXECUTION_PROMPT = {
    "zh": """你是资深media planner。从结案报告中提取【媒介计划+执行细节】信息。

提取规则：
1. 只提取报告中明确提到的信息，不要推测
2. media_plan关注"买什么花多少"：预算分配、tier结构、选择标准
3. execution关注实际执行：用了哪些资源、什么内容形式、哪些供应商
4. tier_breakdown中每个tier应有平台、数量、预算占比（budget_allocated或budget_percentage至少填一个）
5. budget数字保持原文单位（万/k/M），不要转换
6. resources_used只记录付费/合作资源，不含自有渠道
7. actual_timeline记录具体执行日期（如"预热期：3月1-14日"），不是传播节奏模式

注意区分：
- media_plan是"花钱买的东西"（paid media + KOL/KOC采买）
- execution是"实际怎么做的"（包含media_plan的落地 + 自有执行）
- 如果线下活动是花钱购买的渠道资源 → media_plan
- 如果线下活动是自己执行的brand event → execution""",
    "en": """You are a senior media planner. Extract [media plan + execution details] from this recap report.

Rules:
1. Only extract explicitly stated information — do not speculate
2. media_plan: focus on "what to buy and how much to spend" — budget splits, tier structure, selection criteria
3. execution: focus on actual delivery — resources used, content formats, vendors
4. Each tier in tier_breakdown should have platform, count, and budget (budget_allocated or budget_percentage — at least one)
5. Keep budget numbers in original units (万/k/M) — do not convert
6. resources_used: only paid/partnered resources, not owned channels
7. actual_timeline: concrete execution dates (e.g. "Teaser: Mar 1-14"), NOT phase patterns

Key distinctions:
- media_plan = "money spent on purchases" (paid media + KOL/KOC procurement)
- execution = "how it was actually done" (media plan delivery + owned execution)
- Offline event as a purchased channel resource → media_plan
- Offline event as a self-run brand event → execution""",
}

OUTCOME_PROMPT = {
    "zh": """你是资深campaign评估专家。从结案报告中提取【结果+经验教训+客户决策模式】信息。

提取规则：
1. 只提取报告中明确提到的信息，不要推测
2. kpi_results用原文的指标名和数值，保持原始单位
3. best_performing_tier/channel基于报告中的效果对比结论
4. lessons_learned是团队总结的经验，不是你的分析
5. reusable_insights是可以复用到其他项目的通用洞察
6. overall_rating：如果报告有评分就用原值(1-5)，没有就留空

区分lessons_learned和reusable_insights：
- lessons_learned: 这个项目特有的教训（如"预热期太短导致爆发力不足"）
- reusable_insights: 可迁移的通用规律（如"美妆品类小红书种草最佳发布时间为周三晚8点"）

client_learnings提取规则：
- decision_style：客户在这个项目中体现的决策风格（如"偏保守，需要数据支撑"、"重视创意突破"）
- client_approved_directions：客户明确认可的方向或元素
- client_rejected_directions：客户明确否决的方向或元素
- kpi_priorities：客户最关注的KPI指标（按优先级排列）
- communication_notes：与客户沟通的注意事项（如"汇报时先说结论"、"不接受纯英文方案"）""",
    "en": """You are a senior campaign evaluation expert. Extract [results + lessons learned + client decision patterns] from this recap report.

Rules:
1. Only extract explicitly stated information — do not speculate
2. kpi_results: use original metric names and values, keep original units
3. best_performing_tier/channel: based on the report's comparative conclusions
4. lessons_learned: the team's own conclusions, not your analysis
5. reusable_insights: generalizable insights transferable to other projects
6. overall_rating: use report's score (1-5) if given, otherwise leave null

Distinguish lessons_learned vs reusable_insights:
- lessons_learned: project-specific takeaways (e.g. "teaser phase too short, hurt launch impact")
- reusable_insights: transferable patterns (e.g. "beauty category Xiaohongshu optimal posting time is Wed 8PM")

client_learnings extraction rules:
- decision_style: how this client makes decisions (e.g. "conservative, needs data backing", "values creative breakthrough")
- client_approved_directions: directions or elements the client explicitly approved
- client_rejected_directions: directions or elements the client explicitly vetoed
- kpi_priorities: KPIs the client cares about most (in priority order)
- communication_notes: things to remember when communicating with this client""",
}

MAX_REPORT_CHARS = 12000


async def extract_campaign_record(
    report_text: str,
    source_archive_id: str | None = None,
) -> CampaignRecord:
    """Run 3 parallel extraction calls and merge into a single CampaignRecord."""
    lang = detect_language(report_text)
    truncated = report_text[:MAX_REPORT_CHARS]

    background_task = invoke_llm_structured(
        [
            SystemMessage(content=BACKGROUND_PROMPT[lang]),
            HumanMessage(content=truncated),
        ],
        output_schema=ExtractionBackground,
        temperature=0,
        max_tokens=4000,
    )

    execution_task = invoke_llm_structured(
        [
            SystemMessage(content=EXECUTION_PROMPT[lang]),
            HumanMessage(content=truncated),
        ],
        output_schema=ExtractionExecution,
        temperature=0,
        max_tokens=3000,
    )

    outcome_task = invoke_llm_structured(
        [
            SystemMessage(content=OUTCOME_PROMPT[lang]),
            HumanMessage(content=truncated),
        ],
        output_schema=ExtractionOutcome,
        temperature=0,
        max_tokens=2000,
    )

    background, execution, outcome = await asyncio.gather(
        background_task, execution_task, outcome_task,
        return_exceptions=True,
    )

    # Handle partial failures — merge whatever succeeded
    record_data: dict = {}
    confidences: list[Confidence] = []

    if isinstance(background, ExtractionBackground):
        record_data.update(background.model_dump())
        confidences.append(background.confidence)
    else:
        logger.error(f"Background extraction failed: {background}")

    if isinstance(execution, ExtractionExecution):
        record_data.update(execution.model_dump())
        confidences.append(execution.confidence)
    else:
        logger.error(f"Execution extraction failed: {execution}")

    if isinstance(outcome, ExtractionOutcome):
        record_data.update(outcome.model_dump())
        confidences.append(outcome.confidence)
    else:
        logger.error(f"Outcome extraction failed: {outcome}")

    # Overall confidence = worst of the three
    if not confidences:
        overall_confidence = Confidence.LOW
    elif Confidence.LOW in confidences:
        overall_confidence = Confidence.LOW
    elif Confidence.PARTIAL in confidences:
        overall_confidence = Confidence.PARTIAL
    else:
        overall_confidence = Confidence.HIGH

    # Remove per-call confidence fields before merging
    record_data.pop("confidence", None)

    return CampaignRecord(
        **record_data,
        confidence=overall_confidence,
        status=ConfirmationStatus.PENDING,
        source_archive_id=source_archive_id,
    )
