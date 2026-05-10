"""Strategy Agent: two-phase strategy generation with feedback-aware constraints."""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm_structured
from backend.core.agents.schemas import BrandCheckResult, StrategyPhase1Result, StrategyPhase2Result
from backend.core.database.connection import get_database
from backend.core.database.repositories.feedback import FeedbackRepository
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language
from backend.core.rag.retriever import format_results_with_sources, retrieve_for_client

PHASE1_SYSTEM = {
    "zh": "你是资深品牌策略师。基于brief和品牌资料库，输出受众洞察和品牌方向建议。",
    "en": "You are a senior brand strategist. Based on the brief and brand library, provide audience insights and brand direction.",
}

PHASE2_SYSTEM = {
    "zh": "你是资深传播策略师。基于Phase 1洞察和市场调研，产出完整策略方案，包括Big Idea、渠道组合、资源需求、预算分配、KPI和时间线。",
    "en": "You are a senior communications strategist. Based on Phase 1 insights and market research, produce a complete strategy including Big Idea, channel mix, resource needs, budget allocation, KPIs, and timeline.",
}

BRAND_CHECK_SYSTEM = {
    "zh": "你是品牌合规审核员。对比策略输出和品牌规范，判断是否一致。",
    "en": "You are a brand compliance reviewer. Compare strategy output against brand specifications for consistency.",
}


async def run_strategy_phase1(
    brief: dict,
    client_id: str,
    project_id: str | None = None,
    budget: RequestBudget | None = None,
) -> StrategyPhase1Result:
    """Phase 1: audience insights + brand direction from Brief + Brand Library."""
    lang = detect_language(json.dumps(brief, ensure_ascii=False))

    brand_results = await retrieve_for_client(
        brief.get("theme", "") + " " + brief.get("audience", ""),
        client_id,
        project_id,
        top_k=5,
    )
    brand_context = format_results_with_sources(brand_results)

    user_msg = f"Brief:\n{json.dumps(brief, ensure_ascii=False)}\n\nBrand materials:\n{brand_context or 'No brand materials available.'}"

    messages = [
        SystemMessage(content=PHASE1_SYSTEM[lang]),
        HumanMessage(content=user_msg),
    ]

    return await invoke_llm_structured(
        messages, output_schema=StrategyPhase1Result, budget=budget, temperature=0.3, max_tokens=2048
    )


async def run_strategy_phase2(
    brief: dict,
    phase1_insight: dict,
    research_result: dict,
    client_id: str | None = None,
    budget: RequestBudget | None = None,
) -> StrategyPhase2Result:
    """Phase 2: Big Idea + full strategy. Avoids rejected directions from history."""
    lang = detect_language(json.dumps(brief, ensure_ascii=False))

    constraints = ""
    if client_id:
        db = await get_database()
        repo = FeedbackRepository(db)
        rejected = await repo.find_rejected_directions(client_id)
        if rejected:
            rejected_text = "\n".join(f"- {d}" for d in rejected[-10:])
            constraints = (
                f"\n\nAvoid these previously rejected directions:\n{rejected_text}"
            )

    user_msg = (
        f"Phase 1 Insight:\n{json.dumps(phase1_insight, ensure_ascii=False)}\n\n"
        f"Market Research:\n{json.dumps(research_result, ensure_ascii=False)[:3000]}\n\n"
        f"Brief:\n{json.dumps(brief, ensure_ascii=False)}"
        f"{constraints}"
    )

    messages = [
        SystemMessage(content=PHASE2_SYSTEM[lang]),
        HumanMessage(content=user_msg),
    ]

    return await invoke_llm_structured(
        messages, output_schema=StrategyPhase2Result, budget=budget, temperature=0.3, max_tokens=3000
    )


async def run_brand_check(
    strategy_text: str,
    client_id: str,
    budget: RequestBudget | None = None,
) -> BrandCheckResult:
    """Check strategy against brand spec namespace."""
    lang = detect_language(strategy_text)

    brand_results = await retrieve_for_client(
        "brand guidelines tone values positioning", client_id, top_k=5
    )
    brand_spec = format_results_with_sources(brand_results)

    if not brand_spec.strip():
        return BrandCheckResult(passed=True, issues=[])

    user_msg = f"Strategy:\n{strategy_text[:2000]}\n\nBrand spec:\n{brand_spec[:2000]}"

    messages = [
        SystemMessage(content=BRAND_CHECK_SYSTEM[lang]),
        HumanMessage(content=user_msg),
    ]

    return await invoke_llm_structured(
        messages, output_schema=BrandCheckResult, budget=budget, temperature=0, max_tokens=1024
    )
