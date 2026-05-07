"""Strategy Agent: two-phase strategy generation with feedback-aware constraints."""
import json

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.agents.llm import invoke_llm, strip_code_block
from backend.core.database.connection import get_database
from backend.core.database.repositories.feedback import FeedbackRepository
from backend.core.graph.state import RequestBudget
from backend.core.language.detector import detect_language
from backend.core.language.prompts import STRATEGY_PHASE1_PROMPTS, STRATEGY_PHASE2_PROMPTS
from backend.core.rag.retriever import retrieve_for_client

BRAND_CHECK_PROMPT = {
    "zh": """对比以下策略输出和品牌规范，检查是否存在不一致。

策略：{strategy}
品牌规范：{brand_spec}

如果一致输出：{{"passed": true, "issues": []}}
如果有问题输出：{{"passed": false, "issues": ["问题描述"]}}""",

    "en": """Compare the following strategy output against brand specifications and check for inconsistencies.

Strategy: {strategy}
Brand spec: {brand_spec}

If consistent, output: {{"passed": true, "issues": []}}
If issues found, output: {{"passed": false, "issues": ["issue description"]}}""",
}


async def run_strategy_phase1(
    brief: dict,
    client_id: str,
    project_id: str | None = None,
    budget: RequestBudget | None = None,
) -> dict:
    """Phase 1: audience insights + brand direction from Brief + Brand Library (runs parallel with Research)."""
    lang = detect_language(json.dumps(brief, ensure_ascii=False))

    brand_results = await retrieve_for_client(
        brief.get("theme", "") + " " + brief.get("audience", ""),
        client_id,
        project_id,
        top_k=5,
    )
    brand_context = "\n".join([r.text for r in brand_results])

    prompt = STRATEGY_PHASE1_PROMPTS[lang].format(
        brief=json.dumps(brief, ensure_ascii=False),
        brand_context=brand_context or "No brand materials available.",
    )

    text = await invoke_llm(
        [HumanMessage(content=prompt)],
        budget=budget,
        temperature=0.3,
        max_tokens=2048,
    )
    text = strip_code_block(text)

    phase1_data = json.loads(text)
    phase1_data["language"] = lang
    return phase1_data


async def run_strategy_phase2(
    brief: dict,
    phase1_insight: dict,
    research_result: dict,
    client_id: str | None = None,
    budget: RequestBudget | None = None,
) -> dict:
    """Phase 2: Big Idea + full strategy (after Research completes). Avoids rejected directions from history."""
    lang = phase1_insight.get("language", "en")
    insight = json.dumps(phase1_insight, ensure_ascii=False)
    research_summary = json.dumps(research_result, ensure_ascii=False)[:3000]

    # Fetch previously rejected directions for this client
    constraints = ""
    if client_id:
        db = await get_database()
        repo = FeedbackRepository(db)
        rejected = await repo.find_rejected_directions(client_id)
        if rejected:
            rejected_text = "\n".join(f"- {d}" for d in rejected[-10:])
            constraints = (
                f"\n\n⚠️ 以下方向曾被客户否决，请避免：\n{rejected_text}"
                if lang == "zh"
                else f"\n\n⚠️ The client has previously rejected these directions — avoid them:\n{rejected_text}"
            )

    prompt = STRATEGY_PHASE2_PROMPTS[lang].format(
        insight=insight,
        research=research_summary,
        brief=json.dumps(brief, ensure_ascii=False),
    ) + constraints

    text = await invoke_llm(
        [HumanMessage(content=prompt)],
        budget=budget,
        temperature=0.3,
        max_tokens=3000,
    )
    text = strip_code_block(text)

    strategy_data = json.loads(text)
    strategy_data["language"] = lang
    return strategy_data


async def run_brand_check(
    strategy_text: str,
    client_id: str,
    budget: RequestBudget | None = None,
) -> dict:
    """Check strategy against brand spec namespace."""
    lang = detect_language(strategy_text)

    brand_results = await retrieve_for_client(
        "brand guidelines tone values positioning", client_id, top_k=5
    )
    brand_spec = "\n".join([r.text for r in brand_results])

    if not brand_spec.strip():
        return {"passed": True, "issues": [], "note": "No brand spec available for check"}

    prompt = BRAND_CHECK_PROMPT[lang].format(
        strategy=strategy_text[:2000],
        brand_spec=brand_spec[:2000],
    )

    text = await invoke_llm(
        [HumanMessage(content=prompt)],
        budget=budget,
        temperature=0,
        max_tokens=1024,
    )
    text = strip_code_block(text)

    return json.loads(text)
