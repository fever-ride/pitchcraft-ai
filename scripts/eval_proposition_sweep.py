"""
Campaign Knowledge Base — Proposition Count Sweep (Secondary Eval)
===================================================================
Tests proposition quality at different N values (5, 8, 10, 12, 15, 20, 25, 30).

For each N:
  1. Extract propositions from a CampaignRecord at that count
  2. Measure redundancy (pairwise cosine similarity)
  3. Optionally: LLM-judge coverage against ground truth

Coverage check requires:
  - scripts/eval_data/anta_ground_truth.json (manual labels)
  - ANTHROPIC_API_KEY in environment

Redundancy check requires:
  - BGE-M3 embedding service running OR sentence-transformers installed locally

Usage:
    # Redundancy only (fast, no LLM cost):
    python scripts/eval_proposition_sweep.py --record-id <id> --no-coverage

    # Full (redundancy + LLM coverage):
    python scripts/eval_proposition_sweep.py --record-id <id>

Output:
    scripts/eval_data/proposition_sweep.json
    Console comparison table
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from backend.core.database.connection import get_database  # noqa: E402
from backend.core.rag.campaign_index import extract_propositions  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────
TARGET_COUNTS = [5, 8, 10, 12, 15, 20, 25, 30]
REDUNDANCY_THRESHOLD = 0.85
GROUND_TRUTH_PATH = "scripts/eval_data/anta_ground_truth.json"
OUTPUT_PATH = "scripts/eval_data/proposition_sweep.json"
# ─────────────────────────────────────────────────────────────────────────────


# ── Redundancy ────────────────────────────────────────────────────────────────

def redundancy_rate(propositions: list[str], threshold: float = REDUNDANCY_THRESHOLD) -> float:
    """Fraction of proposition pairs with cosine similarity > threshold."""
    if len(propositions) < 2:
        return 0.0
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-m3")
        embeddings = model.encode(propositions, normalize_embeddings=True)
    except ImportError:
        print("  sentence-transformers not installed; skipping redundancy check")
        return -1.0

    n = len(embeddings)
    dup_pairs = 0
    total_pairs = n * (n - 1) // 2
    for i in range(n):
        for j in range(i + 1, n):
            sim = float(np.dot(embeddings[i], embeddings[j]))
            if sim > threshold:
                dup_pairs += 1
    return dup_pairs / total_pairs if total_pairs > 0 else 0.0


# ── Coverage (LLM judge) ──────────────────────────────────────────────────────

async def check_coverage_llm(propositions: list[str], ground_truth: list[dict]) -> float:
    """LLM judge: for each search-triggering GT item, does any proposition cover it?"""
    from langchain_core.messages import HumanMessage, SystemMessage
    from backend.core.agents.llm import invoke_llm_structured
    from pydantic import BaseModel

    class CoverageVerdict(BaseModel):
        covered: bool

    search_triggering = [gt for gt in ground_truth if gt.get("type") == "search-triggering"]
    if not search_triggering:
        print("  No search-triggering items in ground truth; skipping coverage")
        return -1.0

    props_text = "\n".join(f"- {p}" for p in propositions)
    covered_count = 0

    for gt in search_triggering:
        try:
            result = await invoke_llm_structured(
                [
                    SystemMessage(content="You are a retrieval evaluator. Answer only with a JSON object."),
                    HumanMessage(content=(
                        f"Propositions:\n{props_text}\n\n"
                        f"Question: {gt['question']}\n\n"
                        "Does at least one proposition address this question? "
                        "Return {\"covered\": true} or {\"covered\": false}."
                    )),
                ],
                output_schema=CoverageVerdict,
                temperature=0,
                max_tokens=50,
            )
            if result.covered:
                covered_count += 1
        except Exception as e:
            print(f"  Coverage check failed for GT-{gt['id']}: {e}")

    return covered_count / len(search_triggering)


# ── Main sweep ────────────────────────────────────────────────────────────────

async def run_sweep(record: dict, run_coverage: bool) -> list[dict]:
    ground_truth = []
    if run_coverage:
        if os.path.exists(GROUND_TRUTH_PATH):
            with open(GROUND_TRUTH_PATH) as f:
                ground_truth = json.load(f)
            st_count = sum(1 for gt in ground_truth if gt.get("type") == "search-triggering")
            print(f"  Loaded ground truth: {len(ground_truth)} items ({st_count} search-triggering)")
        else:
            print(f"  Ground truth not found at {GROUND_TRUTH_PATH}; skipping coverage")
            run_coverage = False

    results = []
    for n in TARGET_COUNTS:
        print(f"\nN={n}: extracting propositions...", end=" ", flush=True)
        props = await extract_propositions(record, target_count=n)
        actual_count = len(props)
        print(f"got {actual_count}")

        red = redundancy_rate(props)
        cov = -1.0
        if run_coverage and ground_truth:
            print(f"  Running LLM coverage check ({len([g for g in ground_truth if g.get('type')=='search-triggering'])} GT items)...", end=" ", flush=True)
            cov = await check_coverage_llm(props, ground_truth)
            print(f"coverage={cov:.0%}")

        results.append({
            "target_n": n,
            "actual_count": actual_count,
            "redundancy_rate": round(red, 3) if red >= 0 else None,
            "coverage_rate": round(cov, 3) if cov >= 0 else None,
            "propositions": props,
        })

    return results


def print_sweep_table(results: list[dict]):
    print(f"\n{'='*65}")
    print(f"{'N':>4}  {'actual':>7}  {'redundancy':>11}  {'coverage':>10}  note")
    print(f"{'─'*65}")
    for r in results:
        red_str = f"{r['redundancy_rate']:.0%}" if r["redundancy_rate"] is not None else "   n/a"
        cov_str = f"{r['coverage_rate']:.0%}" if r["coverage_rate"] is not None else "   n/a"
        note = " ← current default" if r["target_n"] == 15 else ""
        print(f"{r['target_n']:>4}  {r['actual_count']:>7}  {red_str:>11}  {cov_str:>10}{note}")

    # Simple recommendation
    print(f"\n{'─'*65}")
    viable = [r for r in results if
              (r["redundancy_rate"] is None or r["redundancy_rate"] <= 0.15) and
              (r["coverage_rate"] is None or r["coverage_rate"] >= 0.9)]
    if viable:
        best = min(viable, key=lambda r: r["target_n"])
        print(f"Smallest N meeting targets (redundancy ≤ 15%, coverage ≥ 90%): N={best['target_n']}")
    else:
        print("No N value met both targets — review results manually")


async def main():
    parser = argparse.ArgumentParser(description="Proposition count sweep eval")
    parser.add_argument("--record-id", required=True, help="campaign_record_id to sweep")
    parser.add_argument("--no-coverage", action="store_true", help="Skip LLM coverage check (faster)")
    args = parser.parse_args()

    print(f"Proposition Sweep Eval")
    print(f"Record ID : {args.record_id}")
    print(f"Counts    : {TARGET_COUNTS}")
    print(f"Coverage  : {'disabled' if args.no_coverage else 'enabled (LLM judge)'}\n")

    db = await get_database()
    record = await db["campaign_records"].find_one({"_id": args.record_id})
    if not record:
        print(f"Record {args.record_id} not found in MongoDB")
        return

    print(f"Record found: {record.get('meta', {}).get('industry', '?')} | {record.get('meta', {}).get('campaign_type', '?')}")

    results = await run_sweep(record, run_coverage=not args.no_coverage)
    print_sweep_table(results)

    output = {
        "record_id": args.record_id,
        "target_counts": TARGET_COUNTS,
        "redundancy_threshold": REDUNDANCY_THRESHOLD,
        "results": results,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nFull results saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
