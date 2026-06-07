"""
Ground Truth Generator — Campaign KB Eval
==========================================
Given a campaign_record_id, uses LLM to generate candidate ground truth items
from the record's fields, then saves them for manual review + classification.

You review the output and set "type" to "search-triggering" or "context-only"
for each item before running eval_proposition_sweep.py with coverage.

Usage:
    python scripts/eval_generate_ground_truth.py --record-id <id>

Output:
    scripts/eval_data/anta_ground_truth.json  (review and classify before using)
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.core.agents.llm import invoke_llm_structured  # noqa: E402
from backend.core.database.connection import get_database  # noqa: E402
from backend.core.rag.campaign_index import _record_to_text  # noqa: E402

OUTPUT_PATH = "scripts/eval_data/anta_ground_truth.json"


class GroundTruthItem(BaseModel):
    id: str
    question: str
    source_field: str
    answer_hint: str  # brief hint of the expected answer, for reviewer reference


class GroundTruthList(BaseModel):
    items: list[GroundTruthItem] = Field(default_factory=list)


GT_SYSTEM = """You are building a retrieval evaluation dataset for a campaign knowledge base.

Given a campaign record, generate retrieval questions that cover every field with substantive content.
Each question should be something an AI agent might ask when looking for relevant historical campaigns.

Rules:
1. One question per distinct fact or decision in the record
2. Questions should be phrased as agent queries, not interview questions
   Good: "运动品牌奥运借势三阶段传播节奏"
   Bad:  "What phase structure did this campaign use?"
3. source_field: the exact field path (e.g. "communication_plan.phasing_structure")
4. answer_hint: a brief phrase of the expected answer (helps reviewer classify)
5. Skip fields that are empty, null, or purely metadata (industry, campaign_type — already in filters)
6. Generate 20-30 items covering all substantive content

Do NOT classify as search-triggering or context-only — that is the human reviewer's job."""


async def generate_ground_truth(record: dict) -> list[dict]:
    record_text = _record_to_text(record)
    result = await invoke_llm_structured(
        [
            SystemMessage(content=GT_SYSTEM),
            HumanMessage(content=f"Campaign record:\n\n{record_text}"),
        ],
        output_schema=GroundTruthList,
        temperature=0.2,
        max_tokens=4000,
    )

    items = []
    for item in result.items:
        items.append({
            "id": item.id,
            "question": item.question,
            "source_field": item.source_field,
            "answer_hint": item.answer_hint,
            "type": "FILL_IN",  # reviewer sets: "search-triggering" or "context-only"
        })
    return items


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-id", required=True)
    args = parser.parse_args()

    db = await get_database()
    record = await db["campaign_records"].find_one({"_id": args.record_id})
    if not record:
        print(f"Record {args.record_id} not found")
        return

    meta = record.get("meta", {})
    print(f"Generating ground truth for: {meta.get('industry')} | {meta.get('campaign_type')}")
    print("Running LLM extraction...\n")

    items = await generate_ground_truth(record)
    print(f"Generated {len(items)} ground truth items\n")

    # Print for review
    print(f"{'─'*70}")
    print(f"{'ID':6}  {'Type (FILL_IN)':16}  Question")
    print(f"{'─'*70}")
    for item in items:
        print(f"{item['id']:6}  {item['type']:16}  {item['question'][:60]}")
        print(f"       source: {item['source_field']}")
        print(f"       answer: {item['answer_hint']}")
        print()

    with open(OUTPUT_PATH, "w") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"{'─'*70}")
    print(f"Saved to {OUTPUT_PATH}")
    print()
    print("Next step: open the file and set each item's 'type' to either:")
    print('  "search-triggering"  — agent would query for this → must be in propositions')
    print('  "context-only"       — agents read after finding campaign → no proposition needed')
    print()
    print("Then run:")
    print(f"  python scripts/eval_proposition_sweep.py --record-id {args.record_id}")


if __name__ == "__main__":
    asyncio.run(main())
