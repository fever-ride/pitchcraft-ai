"""Backfill resource profiles: infer tier, content_style_v2, audience_demographics from existing data.

Uses LLM to classify existing resources based on their freeform fields (followers,
content_style, audience_tags, categories, platform). Updates MongoDB and refreshes
Pinecone embeddings.

Usage:
    python scripts/backfill_resource_profiles.py [--dry-run] [--client-id CLIENT_ID] [--batch-size 20]

Options:
    --dry-run       Show what would be inferred without writing to DB
    --client-id     Only backfill resources for a specific client
    --batch-size    Number of resources per LLM batch call (default: 20)
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database.connection import get_database
from backend.core.models.resource import parse_follower_count
from backend.core.rag.resource_import import refresh_resource_embedding

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

INFERENCE_PROMPT = """You are classifying creator/media resources for a media planning system.

For each resource below, infer the following fields based on available data:

1. **tier** (top / mid / tail / koc / null):
   - top: 500K+ followers on major platforms, high production value, brand-level influence
   - mid: 50K-500K followers, niche authority, good engagement
   - tail: 10K-50K followers, micro-influencer
   - koc: <10K followers or explicitly consumer-type
   - null: cannot determine (e.g. media/vendor resources don't have tiers)

2. **content_style_v2** (object or null):
   - production_level: high / medium / low (based on content_style description, platform norms)
   - persona_type: expert / relatable / aspirational / entertaining (infer from categories + content style)
   - voice_style: educational / conversational / emotional / humorous (infer from content description)

3. **audience_demographics** (object or null):
   - age_range: e.g. "18-24", "25-35" (infer from platform + categories)
   - gender_skew: female / male / balanced (infer from categories)
   - city_tier: tier_1 / tier_2_3 / all (infer if possible, otherwise null)
   - interest_tags: list of 2-4 tags (derived from categories + audience_tags)

Rules:
- For media/vendor/placement resources, set tier=null and content_style_v2=null
- Only set fields you can reasonably infer. Use null for uncertain fields.
- Platform norms: 小红书 skews female/young; B站 skews male/young; 抖音 is broad

Return a JSON array with one object per resource, in the same order as input.
Each object: {"index": <int>, "tier": ..., "content_style_v2": {...} or null, "audience_demographics": {...} or null}
"""


def _build_resource_summary(doc: dict) -> str:
    """Build a concise text summary of a resource for LLM classification."""
    parts = [f"Name: {doc.get('name', '')}"]
    parts.append(f"Type: {doc.get('type', '')}")
    if doc.get("platform"):
        parts.append(f"Platform: {doc['platform']}")
    if doc.get("followers"):
        parts.append(f"Followers: {doc['followers']}")
        fc = parse_follower_count(doc.get("followers"))
        if fc:
            parts.append(f"(parsed: {fc})")
    if doc.get("categories"):
        cats = doc["categories"]
        parts.append(f"Categories: {', '.join(cats) if isinstance(cats, list) else cats}")
    if doc.get("content_style"):
        parts.append(f"Content Style: {doc['content_style']}")
    if doc.get("audience_tags"):
        tags = doc["audience_tags"]
        parts.append(f"Audience Tags: {', '.join(tags) if isinstance(tags, list) else tags}")
    if doc.get("tags"):
        tags = doc["tags"]
        parts.append(f"Tags: {', '.join(tags) if isinstance(tags, list) else tags}")
    if doc.get("outlet_type"):
        parts.append(f"Outlet: {doc['outlet_type']}")
    if doc.get("service_type"):
        parts.append(f"Service: {doc['service_type']}")
    return " | ".join(parts)


async def _infer_batch(resources: list[dict], batch_size: int = 20) -> list[dict]:
    """Call LLM to infer profiles for a batch of resources."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from backend.core.agents.llm import get_llm, strip_code_block

    llm = get_llm(temperature=0, max_tokens=4000)

    summaries = []
    for i, doc in enumerate(resources):
        summaries.append(f"[{i}] {_build_resource_summary(doc)}")

    user_msg = "Classify these resources:\n\n" + "\n".join(summaries)

    messages = [
        SystemMessage(content=INFERENCE_PROMPT),
        HumanMessage(content=user_msg),
    ]

    response = await llm.ainvoke(messages)
    text = response.content if hasattr(response, "content") else str(response)
    text = strip_code_block(text)

    try:
        results = json.loads(text)
        if isinstance(results, list):
            return results
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM response as JSON: {text[:200]}")

    return []


async def backfill(dry_run: bool = False, client_id: str | None = None, batch_size: int = 20):
    db = await get_database()
    collection = db["resources"]

    query = {
        "$or": [
            {"tier": {"$exists": False}},
            {"tier": None},
            {"content_style_v2": {"$exists": False}},
            {"audience_demographics": {"$exists": False}},
        ]
    }
    if client_id:
        query["client_id"] = client_id

    cursor = collection.find(query)
    resources = await cursor.to_list(length=None)

    logger.info(f"Found {len(resources)} resources needing profile backfill")

    if not resources:
        return

    if dry_run:
        for r in resources[:10]:
            logger.info(f"  [DRY RUN] Would classify: {r.get('name')} ({r.get('type')}, {r.get('platform', 'no platform')})")
        if len(resources) > 10:
            logger.info(f"  ... and {len(resources) - 10} more")
        return

    updated = 0
    failed = 0

    for i in range(0, len(resources), batch_size):
        batch = resources[i:i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} resources)...")

        try:
            inferences = await _infer_batch(batch, batch_size)
        except Exception as e:
            logger.error(f"  Batch failed: {e}")
            failed += len(batch)
            continue

        for inference in inferences:
            idx = inference.get("index")
            if idx is None or idx >= len(batch):
                continue

            doc = batch[idx]
            update = {}

            tier_val = inference.get("tier")
            if tier_val and tier_val in ("top", "mid", "tail", "koc"):
                update["tier"] = tier_val

            cs = inference.get("content_style_v2")
            if isinstance(cs, dict) and any(cs.values()):
                clean_cs = {k: v for k, v in cs.items() if v is not None}
                if clean_cs:
                    update["content_style_v2"] = clean_cs

            ad = inference.get("audience_demographics")
            if isinstance(ad, dict) and any(ad.values()):
                clean_ad = {k: v for k, v in ad.items() if v is not None}
                if clean_ad:
                    update["audience_demographics"] = clean_ad

            if not update:
                continue

            try:
                await collection.update_one({"_id": doc["_id"]}, {"$set": update})
                # Refresh embedding with new fields
                updated_doc = {**doc, **update}
                cid = doc.get("client_id", "")
                await refresh_resource_embedding(updated_doc, cid)
                updated += 1
                logger.info(f"  Updated: {doc.get('name')} → tier={update.get('tier')}")
            except Exception as e:
                failed += 1
                logger.error(f"  Failed to update {doc.get('name')}: {e}")

    logger.info(f"Backfill complete: {updated} updated, {failed} failed, {len(resources) - updated - failed} skipped")


def main():
    parser = argparse.ArgumentParser(description="Backfill resource tier/content_style_v2/audience_demographics via LLM inference")
    parser.add_argument("--dry-run", action="store_true", help="Show resources to classify without writing")
    parser.add_argument("--client-id", type=str, default=None, help="Only backfill for this client")
    parser.add_argument("--batch-size", type=int, default=20, help="Resources per LLM call (default: 20)")
    args = parser.parse_args()

    asyncio.run(backfill(dry_run=args.dry_run, client_id=args.client_id, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
