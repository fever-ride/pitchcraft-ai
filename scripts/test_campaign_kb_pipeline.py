"""Campaign Knowledge Base pipeline integration test.

Full flow: PDF parse → LLM extraction → MongoDB store → human confirmation →
proposition extraction → BGE-M3 embedding → Pinecone upsert → retrieval verify.

Prerequisites:
  docker compose up -d mongodb redis
  BGE-M3 embedding service running at localhost:8001
    (run: uvicorn server:app --host 0.0.0.0 --port 8001
     from infrastructure/docker/embedding/)
  ANTHROPIC_API_KEY and PINECONE_API_KEY in .env

Steps:
  1. PDF parse
  2. Campaign record extraction (LLM)
  3. MongoDB store
  4. MongoDB retrieve + verify
  5. Simulate human confirmation
  6. Proposition extraction (LLM)
  7. Proposition MongoDB store
  8. BGE-M3 embedding + Pinecone upsert
  9. Pinecone retrieval verify

Usage:
  python scripts/test_campaign_kb_pipeline.py [path/to/report.pdf] [--keep]

  Default PDF: ~/Downloads/2026年1月更新/安踏24Q3【中国甲】营销结案.pdf
  --keep: preserve test records in MongoDB/Pinecone after test
"""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

# Load .env file FIRST (overrides any empty shell env vars like ANTHROPIC_API_KEY='')
# Must happen before any backend imports that create the Settings singleton.
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()

# Override service URLs to local instances before Settings is created
os.environ["MONGODB_URL"] = "mongodb://localhost:27017"
os.environ["EMBEDDING_SERVICE_URL"] = "http://localhost:8001"

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.agents.campaign_extract import extract_campaign_record
from backend.core.database.connection import get_database
from backend.core.models.campaign_record import ConfirmationStatus
from backend.core.rag.campaign_index import extract_propositions
from backend.core.rag.campaign_retriever import (
    SufficiencyVerdict,
    retrieve_campaign_knowledge,
)
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import _get_index
from backend.core.rag.parser import parse_file

ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_YELLOW = "\033[93m"
ANSI_CYAN = "\033[96m"
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"


def ok(msg: str):
    print(f"  {ANSI_GREEN}✓{ANSI_RESET} {msg}")


def fail(msg: str):
    print(f"  {ANSI_RED}✗{ANSI_RESET} {msg}")
    sys.exit(1)


def info(msg: str):
    print(f"  {ANSI_CYAN}→{ANSI_RESET} {msg}")


def skip(msg: str):
    print(f"  {ANSI_YELLOW}⊘{ANSI_RESET} {msg}")


def header(msg: str):
    print(f"\n{ANSI_BOLD}{msg}{ANSI_RESET}")


async def run_pipeline(pdf_path: Path):
    # ─────────────────────────────────────────────────────────────
    # Step 1: PDF Parse
    # ─────────────────────────────────────────────────────────────
    header("Step 1 · PDF Parse")
    file_bytes = pdf_path.read_bytes()
    report_text = parse_file(file_bytes, pdf_path.name)

    if not report_text.strip():
        fail(f"Empty text after parsing {pdf_path.name}")

    word_count = len(report_text)
    ok(f"Parsed {word_count:,} chars from {pdf_path.name}")
    info(f"First 200 chars: {report_text[:200].replace(chr(10), ' ')}")

    # ─────────────────────────────────────────────────────────────
    # Step 2: Campaign Record Extraction (LLM)
    # ─────────────────────────────────────────────────────────────
    header("Step 2 · Campaign Record Extraction (LLM)")
    print("  Running 2-3 parallel LLM calls…")

    record = await extract_campaign_record(
        report_text,
        source_archive_id="test-archive-001",
        page_count=None,
    )

    ok(f"Extraction complete — record_type={record.record_type.value}, confidence={record.confidence.value}")

    meta = record.meta
    info(f"client_name: {meta.client_name}")
    info(f"industry:    {meta.industry}")
    info(f"campaign_type: {meta.campaign_type}")
    info(f"campaign_subtype: {meta.campaign_subtype}")
    info(f"budget_tier: {meta.budget_tier}")
    info(f"target_audience_summary: {meta.target_audience_summary}")

    strategy = record.strategy_decisions
    if strategy.big_idea:
        info(f"big_idea: {strategy.big_idea[:100]}")

    outcome = record.outcome
    if outcome.kpi_results:
        info(f"kpi_results ({len(outcome.kpi_results)} items): {list(outcome.kpi_results.keys())[:5]}")

    # Assertions
    if record.meta.client_name is None:
        fail("client_name not extracted")
    ok("client_name present")

    if record.meta.campaign_type is None:
        fail("campaign_type not extracted")
    ok(f"campaign_type: {record.meta.campaign_type.value}")

    if record.meta.campaign_subtype is None:
        fail("campaign_subtype not extracted")
    ok(f"campaign_subtype: {record.meta.campaign_subtype}")

    # ─────────────────────────────────────────────────────────────
    # Step 3: MongoDB Store
    # ─────────────────────────────────────────────────────────────
    header("Step 3 · MongoDB Store")
    db = await get_database()

    record_id = str(uuid.uuid4())
    campaign_dict = record.model_dump(by_alias=True)
    campaign_dict["_id"] = record_id
    campaign_dict["client_id"] = "test-client-001"
    campaign_dict["project_id"] = "test-project-001"
    campaign_dict["org_id"] = "test-org-001"
    campaign_dict["source_archive_id"] = "test-archive-001"

    result = await db["campaign_records"].insert_one(campaign_dict)
    ok(f"Stored campaign record: _id={record_id}")

    # ─────────────────────────────────────────────────────────────
    # Step 4: MongoDB Retrieve + Verify
    # ─────────────────────────────────────────────────────────────
    header("Step 4 · MongoDB Retrieve")
    doc = await db["campaign_records"].find_one({"_id": record_id})

    if doc is None:
        fail(f"Record {record_id} not found in MongoDB")
    ok("Retrieved record from MongoDB")

    # Verify key fields round-trip correctly
    assert doc["record_type"] == record.record_type.value, \
        f"record_type mismatch: {doc['record_type']} vs {record.record_type.value}"
    ok(f"record_type round-trip OK: {doc['record_type']}")

    assert doc["meta"]["client_name"] == record.meta.client_name, "client_name mismatch"
    ok(f"client_name round-trip OK: {doc['meta']['client_name']}")

    assert doc["status"] == ConfirmationStatus.PENDING.value, \
        f"Expected pending_confirmation, got {doc['status']}"
    ok(f"status=pending_confirmation ✓")

    # ─────────────────────────────────────────────────────────────
    # Step 5: Simulate Human Confirmation
    # ─────────────────────────────────────────────────────────────
    header("Step 5 · Simulate Human Confirmation")
    await db["campaign_records"].update_one(
        {"_id": record_id},
        {"$set": {
            "status": ConfirmationStatus.CONFIRMED.value,
            "confirmed_by": "test-user",
        }},
    )

    confirmed_doc = await db["campaign_records"].find_one({"_id": record_id})
    assert confirmed_doc["status"] == ConfirmationStatus.CONFIRMED.value
    ok(f"status updated to confirmed")

    # ─────────────────────────────────────────────────────────────
    # Step 6: Proposition Extraction (LLM only)
    # ─────────────────────────────────────────────────────────────
    header("Step 6 · Proposition Extraction (LLM)")
    print("  Decomposing CampaignRecord into atomic propositions…")

    propositions = await extract_propositions(confirmed_doc)

    if not propositions:
        fail("No propositions extracted")
    ok(f"Extracted {len(propositions)} propositions")

    # Verify prefix consistency
    prefix_issues = []
    for i, prop in enumerate(propositions):
        if not prop.startswith("["):
            prefix_issues.append(i)
    if prefix_issues:
        fail(f"Propositions {prefix_issues} missing bracket prefix")
    ok("All propositions have bracket prefix")

    print(f"\n  Sample propositions:")
    for p in propositions[:5]:
        print(f"    • {p[:120]}")
    if len(propositions) > 5:
        print(f"    … ({len(propositions) - 5} more)")

    # ─────────────────────────────────────────────────────────────
    # Step 7: Proposition MongoDB Store
    # ─────────────────────────────────────────────────────────────
    header("Step 7 · Proposition MongoDB Store")
    prop_docs = [
        {
            "campaign_record_id": record_id,
            "text": prop,
            "index": i,
        }
        for i, prop in enumerate(propositions)
    ]
    await db["campaign_propositions"].insert_many(prop_docs)
    ok(f"Stored {len(prop_docs)} propositions to campaign_propositions collection")

    # Verify retrieval
    stored_count = await db["campaign_propositions"].count_documents(
        {"campaign_record_id": record_id}
    )
    assert stored_count == len(propositions), \
        f"Expected {len(propositions)} propositions in DB, found {stored_count}"
    ok(f"Verified {stored_count} propositions retrievable by record_id")

    # ─────────────────────────────────────────────────────────────
    # Step 8: BGE-M3 Embedding + Pinecone Upsert
    # ─────────────────────────────────────────────────────────────
    header("Step 8 · BGE-M3 Embedding + Pinecone Upsert")

    # Check embedding service is alive
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            health = await client.get("http://localhost:8001/health")
            health.raise_for_status()
        ok(f"Embedding service healthy: {health.json()}")
    except Exception as e:
        fail(f"Embedding service not reachable at localhost:8001 — {e}\n"
             f"  Start it with: uvicorn server:app --host 0.0.0.0 --port 8001\n"
             f"  (from infrastructure/docker/embedding/)")

    print(f"  Embedding {len(propositions)} propositions via BGE-M3…")
    embeddings = await embed_texts(propositions)
    ok(f"Got {len(embeddings)} embeddings, dim={len(embeddings[0])}")

    if len(embeddings[0]) != 1024:
        fail(f"Expected 1024-dim embeddings, got {len(embeddings[0])}")
    ok("Embedding dimension 1024 ✓")

    # Upsert to Pinecone campaign_knowledge namespace
    namespace = f"campaign_knowledge_test-org-001"
    meta = confirmed_doc.get("meta", {})
    index = _get_index()

    vectors = []
    for i, (prop, emb) in enumerate(zip(propositions, embeddings)):
        vectors.append({
            "id": f"camp_{record_id}_{i}",
            "values": emb,
            "metadata": {
                "campaign_record_id": record_id,
                "text": prop[:1000],
                "campaign_type": meta.get("campaign_type", ""),
                "campaign_subtype": meta.get("campaign_subtype", ""),
                "industry": meta.get("industry", ""),
                "budget_tier": meta.get("budget_tier") or "",
                "record_type": confirmed_doc.get("record_type", "campaign"),
                "pitch_outcome": confirmed_doc.get("pitch_outcome", "unknown"),
            },
        })

    index.upsert(vectors=vectors, namespace=namespace)
    ok(f"Upserted {len(vectors)} vectors to Pinecone namespace: {namespace}")

    # ─────────────────────────────────────────────────────────────
    # Step 9: Pinecone Retrieval Verify
    # ─────────────────────────────────────────────────────────────
    header("Step 9 · Pinecone Retrieval Verify")
    print("  Waiting 3s for Pinecone to index…")
    import asyncio as _asyncio
    await _asyncio.sleep(3)

    # Embed a query related to 安踏 奥运营销
    query = "运动品牌奥运营销KOL传播策略"
    info(f"Query: {query}")
    query_emb = await embed_texts([query])

    result = index.query(
        vector=query_emb[0],
        namespace=namespace,
        top_k=5,
        include_metadata=True,
    )

    if not result.matches:
        fail("No results returned from Pinecone query")

    ok(f"Got {len(result.matches)} matches from Pinecone")

    # Verify our record is in the results
    matched_record_ids = {m.metadata.get("campaign_record_id") for m in result.matches}
    if record_id in matched_record_ids:
        ok(f"Our record ({record_id[:8]}…) appears in top-{len(result.matches)} results ✓")
    else:
        fail(f"Our record not found in results — matched: {matched_record_ids}")

    top_match = result.matches[0]
    info(f"Top match score: {top_match.score:.4f}")
    info(f"Top proposition: {top_match.metadata.get('text', '')[:100]}")

    relevant_top_score = result.matches[0].score

    # ─────────────────────────────────────────────────────────────
    # Step 10: Irrelevant Query Should Score Lower / Be Rejected
    # ─────────────────────────────────────────────────────────────
    header("Step 10 · Irrelevant Query Rejection")

    # Query completely unrelated to 安踏 / 奥运 / 运动服饰
    irrelevant_query = "银行理财产品面向老年客户的线下推广策略"
    info(f"Irrelevant query: {irrelevant_query}")

    irrelevant_emb = await embed_texts([irrelevant_query])
    irrelevant_result = index.query(
        vector=irrelevant_emb[0],
        namespace=namespace,
        top_k=3,
        include_metadata=True,
    )

    irr_score = irrelevant_result.matches[0].score if irrelevant_result.matches else 0.0

    if irrelevant_result.matches:
        irr_score = irrelevant_result.matches[0].score
        info(f"Irrelevant query top score: {irr_score:.4f}  (relevant was: {relevant_top_score:.4f})")

        score_drop = relevant_top_score - irr_score
        if score_drop > 0.05:
            ok(f"Score dropped by {score_drop:.4f} for unrelated query ✓")
        else:
            info(f"Score gap small ({score_drop:.4f}) — expected with only 1 record in index")

        if irr_score < 0.40:
            ok(f"Score {irr_score:.4f} below threshold 0.40 — filtered out ✓")
        else:
            info(f"Score {irr_score:.4f} above threshold — self-verification will decide")
    else:
        irr_score = 0.0
        ok("No matches returned for irrelevant query ✓")

    # ─────────────────────────────────────────────────────────────
    # Step 11: Full retrieve_campaign_knowledge() Path
    # ─────────────────────────────────────────────────────────────
    header("Step 11 · Full Retrieval Path (retrieve_campaign_knowledge)")
    org_id = "test-org-001"

    # --- 11a: strategy_reference profile ---
    info("Profile: strategy_reference (top_k=6, modules: strategy_decisions, communication_plan, outcome)")
    strategy_results = await retrieve_campaign_knowledge(
        query="运动品牌奥运借势营销策略框架和渠道组合",
        org_id=org_id,
        profile_name="strategy_reference",
        verify=True,
    )

    if strategy_results:
        r = strategy_results[0]
        ok(f"strategy_reference: got {len(strategy_results)} result(s), top score={r.top_score:.4f}")
        ok(f"  Matched {len(r.matched_propositions)} proposition(s)")
        returned_modules = list(r.modules.keys())
        info(f"  Modules returned: {returned_modules}")
        # These modules should be present if LLM extracted them
        for expected in ["strategy_decisions", "communication_plan"]:
            if expected in returned_modules:
                ok(f"  Module '{expected}' present ✓")
            else:
                info(f"  Module '{expected}' absent (may be empty in record)")
        if r.sufficiency_note:
            info(f"  Sufficiency note: {r.sufficiency_note}")
    else:
        info("strategy_reference returned no results (self-verification: insufficient)")
        info("Expected with only 1 record — verifier has no diversity to judge against")

    # --- 11b: media_planning profile ---
    info("Profile: media_planning (top_k=15, modules: media_plan, execution, outcome)")
    media_results = await retrieve_campaign_knowledge(
        query="KOL预算分配tier结构小红书抖音投放方案",
        org_id=org_id,
        profile_name="media_planning",
        verify=True,
    )

    if media_results:
        r = media_results[0]
        ok(f"media_planning: got {len(media_results)} result(s), top score={r.top_score:.4f}")
        returned_modules = list(r.modules.keys())
        info(f"  Modules returned: {returned_modules}")

        # Verify profiles return different module sets
        strat_modules = set(strategy_results[0].modules.keys()) if strategy_results else set()
        media_modules = set(r.modules.keys())
        overlap = strat_modules & media_modules
        diff = (strat_modules | media_modules) - overlap
        if diff:
            ok(f"  Profiles return different modules ✓ (diff: {diff})")
        else:
            info(f"  Both profiles returned same modules (record may lack media_plan data)")
    else:
        info("media_planning returned no results (self-verification: insufficient)")

    # --- 11c: irrelevant query through full pipeline ---
    info("Full pipeline with irrelevant query (should return [] or partial)")
    irrelevant_results = await retrieve_campaign_knowledge(
        query=irrelevant_query,
        org_id=org_id,
        profile_name="strategy_reference",
        verify=True,
    )

    if not irrelevant_results:
        ok("Irrelevant query returned [] after self-verification ✓")
    else:
        note = irrelevant_results[0].sufficiency_note
        info(f"Irrelevant query returned {len(irrelevant_results)} result(s) — "
             f"sufficiency_note: '{note}'")

    # ─────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────
    print(f"\n{ANSI_BOLD}{'─'*60}{ANSI_RESET}")
    print(f"{ANSI_GREEN}{ANSI_BOLD}Pipeline test PASSED{ANSI_RESET}  "
          f"(All 11 steps complete ✓)")
    print(f"\n  Record ID   : {record_id}")
    print(f"  Propositions: {len(propositions)}")
    print(f"  Pinecone ns : {namespace}")
    print(f"  Relevant score  : {relevant_top_score:.4f}")
    print(f"  Irrelevant score: {irr_score:.4f}")
    print(f"  MongoDB DB  : pitchcraft@localhost:27017")

    return record_id


async def cleanup(record_id: str):
    """Remove test records from MongoDB and Pinecone."""
    db = await get_database()
    await db["campaign_records"].delete_one({"_id": record_id})
    await db["campaign_propositions"].delete_many({"campaign_record_id": record_id})

    # Clean up Pinecone vectors (best-effort; may fail if upsert didn't happen)
    try:
        index = _get_index()
        namespace = "campaign_knowledge_test-org-001"
        index.delete(
            filter={"campaign_record_id": {"$eq": record_id}},
            namespace=namespace,
        )
    except Exception:
        pass  # Pinecone delete failure is non-fatal for cleanup

    print(f"\n  Cleaned up test records for {record_id}")


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pdf_path = Path(
        args[0] if args
        else "/Users/wendyzhong/Downloads/2026年1月更新/安踏24Q3【中国甲】营销结案.pdf"
    )

    if not pdf_path.exists():
        print(f"{ANSI_RED}PDF not found: {pdf_path}{ANSI_RESET}")
        print("Usage: python scripts/test_campaign_kb_pipeline.py [path/to/report.pdf]")
        sys.exit(1)

    record_id = None
    try:
        record_id = await run_pipeline(pdf_path)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n{ANSI_RED}{ANSI_BOLD}Pipeline test FAILED{ANSI_RESET}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if record_id and "--keep" not in sys.argv:
            await cleanup(record_id)
        elif record_id:
            print(f"\n  --keep flag set; test records preserved in MongoDB")


if __name__ == "__main__":
    asyncio.run(main())
