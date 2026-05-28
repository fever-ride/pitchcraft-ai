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
    "zh": """你是资深整合营销执行专家。从结案报告中提取【媒介计划+执行细节】信息。

项目可能是纯广告投放、纯公关传播、或两者混合——请根据报告实际内容提取，不要遗漏任何一类执行内容。

提取规则：
1. 只提取报告中明确提到的信息，不要推测
2. media_plan关注付费采买：KOL/KOC投放预算、媒介购买、tier结构和选择标准
3. execution.resources_used记录具体合作资源（KOL、媒体、供应商等）
4. execution.activities记录不属于付费采买的执行动作，例如：
   - 公关活动：媒体沟通会、新闻发布会、专家背书、媒体探店
   - 线下活动：快闪店、发布会、品鉴会、快闪活动
   - 内容合作：联名、跨界、UGC征集
   - 其他：直播、话题营销、危机公关处理
5. budget数字保持原文单位（万/k/M），不要转换
6. actual_timeline记录具体执行日期，不是传播节奏模式

注意：
- 广告投放项目：media_plan字段内容丰富，activities可能较少
- 公关项目：activities字段内容丰富，media_plan可能较少
- 整合项目：两者都填""",
    "en": """You are a senior integrated marketing execution expert. Extract [media plan + execution details] from this recap report.

The campaign may be pure advertising, pure PR, or an integrated mix — extract all execution content present in the report without skipping any category.

Rules:
1. Only extract explicitly stated information — do not speculate
2. media_plan: focus on paid purchases — KOL/KOC spend, media buys, tier structure and selection criteria
3. execution.resources_used: specific partners (KOLs, media outlets, vendors)
4. execution.activities: execution actions that are NOT paid purchases, e.g.:
   - PR activities: media briefings, press conferences, expert endorsements, media visits
   - Offline events: pop-ups, launch events, tastings, experiential activations
   - Content collaborations: co-branding, crossovers, UGC campaigns
   - Other: livestreams, hashtag campaigns, crisis response
5. Keep budget numbers in original units (万/k/M) — do not convert
6. actual_timeline: concrete execution dates, NOT phase patterns

Note:
- Advertising-heavy campaigns: media_plan will be rich, activities may be sparse
- PR-heavy campaigns: activities will be rich, media_plan may be sparse
- Integrated campaigns: fill both""",
}

OUTCOME_PROMPT = {
    "zh": """你是资深campaign评估专家。从结案报告中提取【活动结果+经验教训】信息。

提取规则：
1. 只提取报告中明确提到的信息，不要推测
2. kpi_results用原文的指标名和数值，保持原始单位
3. best_performing_tier/channel基于报告中的效果对比结论
4. lessons_learned是团队总结的经验，不是你的分析
5. reusable_insights是可以复用到其他项目的通用洞察
6. overall_rating：如果报告有评分就用原值(1-5)，没有就留空

区分lessons_learned和reusable_insights：
- lessons_learned: 这个项目特有的教训（如"预热期太短导致爆发力不足"）
- reusable_insights: 可迁移的通用规律（如"美妆品类小红书种草最佳发布时间为周三晚8点"）""",
    "en": """You are a senior campaign evaluation expert. Extract [campaign results + lessons learned] from this recap report.

Rules:
1. Only extract explicitly stated information — do not speculate
2. kpi_results: use original metric names and values, keep original units
3. best_performing_tier/channel: based on the report's comparative conclusions
4. lessons_learned: the team's own conclusions, not your analysis
5. reusable_insights: generalizable insights transferable to other projects
6. overall_rating: use report's score (1-5) if given, otherwise leave null

Distinguish lessons_learned vs reusable_insights:
- lessons_learned: project-specific takeaways (e.g. "teaser phase too short, hurt launch impact")
- reusable_insights: transferable patterns (e.g. "beauty category Xiaohongshu optimal posting time is Wed 8PM")""",
}

# Call 1 & 2: strategy and execution info is front-loaded in most reports.
FRONT_MAX_CHARS = 40000

# Call 3: outcome data lives at the end of the report.
OUTCOME_TAIL_CHARS = 20000

# If Call 3 returns empty outcome fields, retry with the section just before the tail.
OUTCOME_MIDDLE_CHARS = 20000


def _slice_for_outcome(text: str) -> str:
    """Return the tail of the report where KPI results and retrospectives live."""
    return text[-OUTCOME_TAIL_CHARS:]


def _outcome_is_empty(outcome: ExtractionOutcome) -> bool:
    """True when all three key outcome fields came back empty."""
    return (
        not outcome.outcome.kpi_results
        and not outcome.outcome.lessons_learned
        and not outcome.outcome.reusable_insights
    )


async def _retry_outcome_with_middle(
    report_text: str,
    lang: str,
) -> ExtractionOutcome:
    """Retry Call 3 on the section just before the tail that was skipped."""
    tail_start = max(0, len(report_text) - OUTCOME_TAIL_CHARS)
    middle_start = max(0, tail_start - OUTCOME_MIDDLE_CHARS)
    middle = report_text[middle_start:tail_start]
    logger.info("Outcome fields empty after tail pass — retrying with preceding section")
    result = await invoke_llm_structured(
        [
            SystemMessage(content=OUTCOME_PROMPT[lang]),
            HumanMessage(content=middle),
        ],
        output_schema=ExtractionOutcome,
        temperature=0,
        max_tokens=2000,
    )
    return result


async def extract_campaign_record(
    report_text: str,
    source_archive_id: str | None = None,
) -> CampaignRecord:
    """Run 3 parallel extraction calls and merge into a single CampaignRecord."""
    lang = detect_language(report_text)

    front_text = report_text[:FRONT_MAX_CHARS]
    outcome_text = _slice_for_outcome(report_text)

    background_task = invoke_llm_structured(
        [
            SystemMessage(content=BACKGROUND_PROMPT[lang]),
            HumanMessage(content=front_text),
        ],
        output_schema=ExtractionBackground,
        temperature=0,
        max_tokens=4000,
    )

    execution_task = invoke_llm_structured(
        [
            SystemMessage(content=EXECUTION_PROMPT[lang]),
            HumanMessage(content=front_text),
        ],
        output_schema=ExtractionExecution,
        temperature=0,
        max_tokens=3000,
    )

    outcome_task = invoke_llm_structured(
        [
            SystemMessage(content=OUTCOME_PROMPT[lang]),
            HumanMessage(content=outcome_text),
        ],
        output_schema=ExtractionOutcome,
        temperature=0,
        max_tokens=2000,
    )

    background, execution, outcome = await asyncio.gather(
        background_task, execution_task, outcome_task,
        return_exceptions=True,
    )

    # If the report was long enough that head+tail slicing skipped the middle,
    # and Call 3 came back empty, retry once with the middle section.
    report_has_middle = len(report_text) > OUTCOME_TAIL_CHARS
    if (
        isinstance(outcome, ExtractionOutcome)
        and _outcome_is_empty(outcome)
        and report_has_middle
    ):
        try:
            outcome = await _retry_outcome_with_middle(report_text, lang)
        except Exception as e:
            logger.error(f"Outcome middle-section retry failed: {e}")

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
