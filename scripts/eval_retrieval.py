"""
Campaign Knowledge Base — Retrieval Quality Eval
=================================================
Primary test: Recall@K, Precision@K, MRR, False Positive Rate

Runs retrieval twice per query:
  - verify=False  → raw vector search, no self-verification gate
  - verify=True   → with self-verification gate (production behaviour)

Comparison shows the gate's impact on FPR.

Usage:
    python scripts/eval_retrieval.py

Prerequisites:
    1. Services running: MongoDB, Redis, BGE-M3 embedding service, Pinecone configured
    2. 6 campaign records archived + confirmed (安踏 + 5 others)
    3. scripts/eval_data/query_set.json filled with real campaign_record_id values
       (replace ANTA_ID / MINI_ID / ... placeholders)

Output:
    scripts/eval_data/eval_results.json   full per-query results
    Console summary table
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Load .env (needed for ANTHROPIC_API_KEY used by the self-verification gate)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()

os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017")
os.environ.setdefault("EMBEDDING_SERVICE_URL", "http://localhost:8001")

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.core.database.connection import get_database  # noqa: E402
from backend.core.rag.campaign_retriever import retrieve_campaign_knowledge  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────
ORG_ID = "test-org-001"          # match the org_id used when archiving records
PROFILE = "strategy_reference"   # use the most general profile for eval
K = 3                             # Recall@K, Precision@K
QUERY_SET_PATH = "scripts/eval_data/query_set.json"
OUTPUT_PATH = "scripts/eval_data/eval_results.json"
# ─────────────────────────────────────────────────────────────────────────────


# ── Metric helpers ────────────────────────────────────────────────────────────

def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Fraction of relevant records that appear in top-K results."""
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    hits = sum(1 for rid in relevant_ids if rid in top_k)
    return hits / len(relevant_ids)


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Fraction of top-K results that are actually relevant."""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant_ids)
    hits = sum(1 for rid in top_k if rid in relevant_set)
    return hits / len(top_k)


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """1 / rank of the first relevant result. 0.0 if not found."""
    relevant_set = set(relevant_ids)
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_set:
            return 1.0 / rank
    return 0.0


# ── Core eval ─────────────────────────────────────────────────────────────────

async def run_single_query(query_obj: dict, verify: bool) -> dict:
    query = query_obj["query"]
    relevant_ids = query_obj["relevant_ids"]

    try:
        results = await retrieve_campaign_knowledge(
            query=query,
            org_id=ORG_ID,
            profile_name=PROFILE,
            verify=verify,
        )
        retrieved_ids = [r.record_id for r in results]
        top_score = results[0].top_score if results else 0.0
    except Exception as e:
        print(f"  ERROR on '{query[:40]}': {e}")
        retrieved_ids = []
        top_score = 0.0

    return {
        "query_id": query_obj["id"],
        "query": query,
        "type": query_obj["type"],
        "relevant_ids": relevant_ids,
        "retrieved_ids": retrieved_ids,
        "top_score": round(top_score, 4),
        "recall_at_k":    round(recall_at_k(retrieved_ids, relevant_ids, K), 3),
        "precision_at_k": round(precision_at_k(retrieved_ids, relevant_ids, K), 3),
        "rr":             round(reciprocal_rank(retrieved_ids, relevant_ids), 3),
    }


async def run_eval(queries: list[dict], verify: bool) -> list[dict]:
    label = "with gate" if verify else "raw (no gate)"
    print(f"\n{'─'*60}")
    print(f"Running retrieval eval — {label}")
    print(f"{'─'*60}")
    results = []
    for q in queries:
        if "note" in q and "id" not in q:
            continue  # skip comment objects
        r = await run_single_query(q, verify=verify)
        status = "✓" if r["recall_at_k"] == 1.0 else "✗" if r["relevant_ids"] and r["recall_at_k"] == 0 else "~"
        print(f"  [{status}] {q['id']:5s} {q['type']:12s}  R@{K}={r['recall_at_k']:.0%}  P@{K}={r['precision_at_k']:.0%}  RR={r['rr']:.2f}  score={r['top_score']:.3f}")
        results.append(r)
    return results


def compute_summary(results: list[dict]) -> dict:
    relevant_qs    = [r for r in results if r["type"] != "irrelevant" and r["relevant_ids"]]
    irrelevant_qs  = [r for r in results if r["type"] == "irrelevant"]
    broad_qs       = [r for r in relevant_qs if r["type"] == "broad"]
    specific_qs    = [r for r in relevant_qs if r["type"] == "specific"]
    crossfield_qs  = [r for r in relevant_qs if r["type"] == "cross-field"]

    def avg(lst, key):
        return round(sum(x[key] for x in lst) / len(lst), 3) if lst else None

    false_positives = [r for r in irrelevant_qs if r["retrieved_ids"]]

    return {
        "total_queries": len(results),
        "relevant_queries": len(relevant_qs),
        "irrelevant_queries": len(irrelevant_qs),
        "recall_at_k":       avg(relevant_qs, "recall_at_k"),
        "precision_at_k":    avg(relevant_qs, "precision_at_k"),
        "mrr":               avg(relevant_qs, "rr"),
        "false_positive_rate": round(len(false_positives) / len(irrelevant_qs), 3) if irrelevant_qs else None,
        "by_type": {
            "broad":       {"recall": avg(broad_qs, "recall_at_k"),      "precision": avg(broad_qs, "precision_at_k"),      "mrr": avg(broad_qs, "rr")},
            "specific":    {"recall": avg(specific_qs, "recall_at_k"),   "precision": avg(specific_qs, "precision_at_k"),   "mrr": avg(specific_qs, "rr")},
            "cross-field": {"recall": avg(crossfield_qs, "recall_at_k"), "precision": avg(crossfield_qs, "precision_at_k"), "mrr": avg(crossfield_qs, "rr")},
        },
    }


def print_summary(summary: dict, label: str):
    print(f"\n{'='*60}")
    print(f"SUMMARY — {label}")
    print(f"{'='*60}")
    print(f"  Recall@{K}    : {summary['recall_at_k']:.0%}" if summary['recall_at_k'] is not None else "  Recall@K : n/a")
    print(f"  Precision@{K} : {summary['precision_at_k']:.0%}" if summary['precision_at_k'] is not None else "  Precision@K: n/a")
    print(f"  MRR         : {summary['mrr']:.2f}" if summary['mrr'] is not None else "  MRR: n/a")
    print(f"  FPR         : {summary['false_positive_rate']:.0%}" if summary['false_positive_rate'] is not None else "  FPR: n/a")
    print()
    print(f"  By query type:")
    for qtype, metrics in summary["by_type"].items():
        r = f"{metrics['recall']:.0%}" if metrics["recall"] is not None else "n/a"
        p = f"{metrics['precision']:.0%}" if metrics["precision"] is not None else "n/a"
        m = f"{metrics['mrr']:.2f}" if metrics["mrr"] is not None else "n/a"
        print(f"    {qtype:12s}  R@{K}={r}  P@{K}={p}  MRR={m}")


# ── Sanity check ──────────────────────────────────────────────────────────────

async def check_placeholders(queries: list[dict]) -> bool:
    """Warn if query_set.json still has unfilled placeholder IDs."""
    placeholders = {"ANTA_ID", "MINI_ID", "MEITUAN_ID", "COSTA_ID", "POPCHRIO_ID", "STOKKE_ID"}
    found = set()
    for q in queries:
        if "relevant_ids" in q:
            for rid in q["relevant_ids"]:
                if rid in placeholders:
                    found.add(rid)
    if found:
        print(f"\n⚠️  query_set.json still has unfilled placeholders: {found}")
        print("   Fill in real campaign_record_id values before running.\n")
        return False
    return True


async def check_records_exist(queries: list[dict]) -> bool:
    """Verify that all relevant_ids in the query set exist in MongoDB."""
    all_ids = set()
    for q in queries:
        if "relevant_ids" in q:
            all_ids.update(q["relevant_ids"])
    all_ids.discard("")

    db = await get_database()
    found = set()
    async for doc in db["campaign_records"].find({"_id": {"$in": list(all_ids)}}):
        found.add(str(doc["_id"]))

    missing = all_ids - found
    if missing:
        print(f"\n⚠️  Records not found in MongoDB: {missing}")
        print("   Archive and confirm these documents first.\n")
        return False
    print(f"  ✓ All {len(all_ids)} referenced records found in MongoDB")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    print("Campaign KB — Retrieval Quality Eval")
    print(f"ORG_ID={ORG_ID}  PROFILE={PROFILE}  K={K}\n")

    with open(QUERY_SET_PATH) as f:
        raw = json.load(f)
    queries = [q for q in raw if "id" in q]  # skip comment objects
    print(f"Loaded {len(queries)} queries from {QUERY_SET_PATH}")

    if not await check_placeholders(queries):
        return
    if not await check_records_exist(queries):
        return

    # Run without self-verification gate (raw vector search)
    raw_results = await run_eval(queries, verify=False)
    raw_summary = compute_summary(raw_results)
    print_summary(raw_summary, f"RAW (verify=False, K={K})")

    # Run with self-verification gate (production behaviour)
    gate_results = await run_eval(queries, verify=True)
    gate_summary = compute_summary(gate_results)
    print_summary(gate_summary, f"WITH GATE (verify=True, K={K})")

    # Show gate impact
    print(f"\n{'─'*60}")
    print("GATE IMPACT (raw → with gate)")
    print(f"{'─'*60}")
    if raw_summary["recall_at_k"] and gate_summary["recall_at_k"]:
        delta_r = gate_summary["recall_at_k"] - raw_summary["recall_at_k"]
        print(f"  Recall@{K}  : {raw_summary['recall_at_k']:.0%} → {gate_summary['recall_at_k']:.0%}  ({delta_r:+.0%})")
    if raw_summary["false_positive_rate"] and gate_summary["false_positive_rate"] is not None:
        delta_fpr = gate_summary["false_positive_rate"] - raw_summary["false_positive_rate"]
        print(f"  FPR       : {raw_summary['false_positive_rate']:.0%} → {gate_summary['false_positive_rate']:.0%}  ({delta_fpr:+.0%})")

    # Save full results
    output = {
        "config": {"org_id": ORG_ID, "profile": PROFILE, "k": K},
        "raw": {"summary": raw_summary, "queries": raw_results},
        "with_gate": {"summary": gate_summary, "queries": gate_results},
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nFull results saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
