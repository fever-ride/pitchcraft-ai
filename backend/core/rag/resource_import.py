"""Resource Excel import: parse .xlsx, create DB records, embed, upsert to Pinecone."""
import io
from collections import defaultdict
from datetime import datetime

from openpyxl import load_workbook

from backend.core.database.connection import get_database
from backend.core.models.resource import ResourceStatus, normalize_platform, parse_follower_count, resource_namespace
from backend.core.rag.embedder import embed_texts
from backend.core.rag.indexer import upsert_vectors

VALID_TYPES = {"kol", "koc", "media", "vendor", "placement"}

KNOWN_COLUMNS = {
    "name", "type", "tier", "platform", "followers", "categories",
    "content_style", "production_level", "persona_type", "voice_style",
    "audience_tags", "age_range", "gender_skew", "city_tier", "interest_tags",
    "past_cpe", "tags", "pricing", "notes",
    "outlet_type", "beat", "service_type", "region",
    "placement_type", "location", "audience_reach",
}

HEADER_ALIASES = {
    "姓名": "name",
    "名称": "name",
    "资源名称": "name",
    "类型": "type",
    "层级": "tier",
    "达人层级": "tier",
    "平台": "platform",
    "粉丝数": "followers",
    "粉丝": "followers",
    "品类": "categories",
    "擅长品类": "categories",
    "内容风格": "content_style",
    "风格": "content_style",
    "制作水平": "production_level",
    "人设类型": "persona_type",
    "表达风格": "voice_style",
    "受众": "audience_tags",
    "受众标签": "audience_tags",
    "年龄段": "age_range",
    "受众年龄": "age_range",
    "性别倾向": "gender_skew",
    "城市级别": "city_tier",
    "兴趣标签": "interest_tags",
    "历史cpe": "past_cpe",
    "cpe": "past_cpe",
    "标签": "tags",
    "报价": "pricing",
    "价格": "pricing",
    "备注": "notes",
    "媒体类型": "outlet_type",
    "跑线": "beat",
    "领域": "beat",
    "服务类型": "service_type",
    "区域": "region",
    "地区": "region",
    "广告类型": "placement_type",
    "位置": "location",
    "覆盖人群": "audience_reach",
}


class ImportParseResult:
    def __init__(self, resources: list[dict], recognized: list[str], ignored: list[str]):
        self.resources = resources
        self.recognized_columns = recognized
        self.ignored_columns = ignored


def parse_resource_excel(file_bytes: bytes) -> ImportParseResult:
    """Parse xlsx bytes into list of resource dicts with column recognition feedback."""
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.close()
        return ImportParseResult([], [], [])

    raw_headers = [str(h).strip() if h else "" for h in rows[0]]

    # Map headers: try lowercase match, then alias lookup
    mapped_headers = []
    recognized = []
    ignored = []
    for h in raw_headers:
        normalized = h.lower()
        if normalized in KNOWN_COLUMNS:
            mapped_headers.append(normalized)
            recognized.append(h)
        elif normalized in HEADER_ALIASES:
            mapped_headers.append(HEADER_ALIASES[normalized])
            recognized.append(h)
        else:
            mapped_headers.append("")
            if h:
                ignored.append(h)

    resources = []
    for row in rows[1:]:
        if not any(row):
            continue
        record = {}
        for idx, header in enumerate(mapped_headers):
            if not header:
                continue
            val = row[idx] if idx < len(row) else None
            if val is not None:
                record[header] = str(val).strip()
        if record.get("name"):
            record.setdefault("type", "kol")
            record.setdefault("platform", "")
            record.setdefault("tags", "")
            record.setdefault("categories", "")
            record.setdefault("content_style", "")
            record.setdefault("audience_tags", "")
            record.setdefault("past_cpe", "")
            record["followers_count"] = parse_follower_count(record.get("followers"))
            record["platform_normalized"] = normalize_platform(record.get("platform", ""))
            record["status"] = ResourceStatus.ACTIVE.value
            record["last_verified_at"] = datetime.utcnow()
            for list_field in ("categories", "audience_tags", "tags", "interest_tags"):
                val = record.get(list_field, "")
                if isinstance(val, str):
                    record[list_field] = [t.strip() for t in val.split(",") if t.strip()]
            # Assemble structured content_style_v2 from individual columns
            cs_v2 = {}
            for cs_field in ("production_level", "persona_type", "voice_style"):
                val = record.pop(cs_field, None)
                if val:
                    cs_v2[cs_field] = val
            if cs_v2:
                record["content_style_v2"] = cs_v2
            # Assemble structured audience_demographics from individual columns
            ad = {}
            for ad_field in ("age_range", "gender_skew", "city_tier"):
                val = record.pop(ad_field, None)
                if val:
                    ad[ad_field] = val
            interest = record.pop("interest_tags", [])
            if interest:
                ad["interest_tags"] = interest
            if ad:
                record["audience_demographics"] = ad
            # Normalize tier
            tier_val = record.get("tier", "")
            if tier_val and tier_val.lower() in ("top", "mid", "tail", "koc"):
                record["tier"] = tier_val.lower()
            else:
                record.pop("tier", None)
            resources.append(record)

    wb.close()
    return ImportParseResult(resources, recognized, ignored)


def _resource_to_text(r: dict) -> str:
    """Convert resource dict to searchable text for embedding."""
    parts = [
        f"Name: {r.get('name', '')}",
        f"Type: {r.get('type', '')}",
    ]
    if r.get("tier"):
        parts.append(f"Tier: {r['tier']}")
    if r.get("platform"):
        parts.append(f"Platform: {r['platform']}")
    if r.get("followers"):
        parts.append(f"Followers: {r['followers']}")
    if r.get("categories"):
        cats = r["categories"]
        parts.append(f"Categories: {', '.join(cats) if isinstance(cats, list) else cats}")
    # Structured content style (v2)
    cs = r.get("content_style_v2")
    if isinstance(cs, dict):
        style_parts = []
        if cs.get("production_level"):
            style_parts.append(f"production:{cs['production_level']}")
        if cs.get("persona_type"):
            style_parts.append(f"persona:{cs['persona_type']}")
        if cs.get("voice_style"):
            style_parts.append(f"voice:{cs['voice_style']}")
        if style_parts:
            parts.append(f"Content Style: {', '.join(style_parts)}")
    elif r.get("content_style"):
        parts.append(f"Content Style: {r['content_style']}")
    # Structured audience demographics
    ad = r.get("audience_demographics")
    if isinstance(ad, dict):
        demo_parts = []
        if ad.get("age_range"):
            demo_parts.append(f"age:{ad['age_range']}")
        if ad.get("gender_skew"):
            demo_parts.append(ad["gender_skew"])
        if ad.get("city_tier"):
            demo_parts.append(ad["city_tier"])
        if ad.get("interest_tags"):
            demo_parts.extend(ad["interest_tags"])
        if demo_parts:
            parts.append(f"Audience: {', '.join(demo_parts)}")
    elif r.get("audience_tags"):
        tags = r["audience_tags"]
        parts.append(f"Audience: {', '.join(tags) if isinstance(tags, list) else tags}")
    if r.get("past_cpe"):
        parts.append(f"Past CPE: {r['past_cpe']}")
    if r.get("tags"):
        tags = r["tags"]
        parts.append(f"Tags: {', '.join(tags) if isinstance(tags, list) else tags}")
    if r.get("pricing"):
        parts.append(f"Pricing: {r['pricing']}")
    if r.get("notes"):
        parts.append(f"Notes: {r['notes']}")
    # Media-specific
    if r.get("outlet_type"):
        parts.append(f"Outlet: {r['outlet_type']}")
    if r.get("beat"):
        parts.append(f"Beat: {r['beat']}")
    # Vendor-specific
    if r.get("service_type"):
        parts.append(f"Service: {r['service_type']}")
    if r.get("region"):
        parts.append(f"Region: {r['region']}")
    # Placement-specific
    if r.get("placement_type"):
        parts.append(f"Placement: {r['placement_type']}")
    if r.get("location"):
        parts.append(f"Location: {r['location']}")
    if r.get("audience_reach"):
        parts.append(f"Reach: {r['audience_reach']}")
    return " | ".join(parts)


async def refresh_resource_embedding(doc: dict, client_id: str):
    """Re-embed a single resource and upsert to Pinecone. Used after any field update."""
    rtype = doc.get("type", "kol").lower()
    if rtype not in VALID_TYPES:
        rtype = "kol"
    ns = resource_namespace(rtype, client_id)
    text = _resource_to_text(doc)
    embeddings = await embed_texts([text])
    resource_id = str(doc.get("_id", ""))
    extra_meta = {
        "name": doc.get("name", ""),
        "type": doc.get("type", rtype),
        "tier": doc.get("tier", ""),
        "platform": normalize_platform(doc.get("platform", "")),
        "status": doc.get("status", ResourceStatus.ACTIVE.value),
        "followers_count": doc.get("followers_count") or 0,
        "tags": ", ".join(doc.get("tags", [])) if isinstance(doc.get("tags"), list) else doc.get("tags", ""),
    }
    upsert_vectors(ns, resource_id, [text], embeddings, extra_metadata=[extra_meta])


async def import_resources(file_bytes: bytes, client_id: str) -> dict:
    """Full import pipeline: parse → DB → embed → Pinecone (grouped by type)."""
    parse_result = parse_resource_excel(file_bytes)
    resources = parse_result.resources
    if not resources:
        return {
            "imported": 0,
            "error": "No valid rows found",
            "recognized_columns": parse_result.recognized_columns,
            "ignored_columns": parse_result.ignored_columns,
        }

    db = await get_database()
    collection = db["resources"]

    for r in resources:
        r["client_id"] = client_id
        await collection.insert_one(r)

    # Group by type for namespace-specific upsert
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in resources:
        rtype = r.get("type", "kol").lower()
        if rtype not in VALID_TYPES:
            rtype = "kol"
        by_type[rtype].append(r)

    namespaces_used = []
    for rtype, group in by_type.items():
        ns = resource_namespace(rtype, client_id)
        texts = [_resource_to_text(r) for r in group]
        embeddings = await embed_texts(texts)
        batch_id = f"import_{client_id}_{rtype}_{len(group)}"

        extra_metadata = []
        for r in group:
            meta = {
                "name": r.get("name", ""),
                "type": r.get("type", rtype),
                "platform": r.get("platform_normalized", normalize_platform(r.get("platform", ""))),
                "status": r.get("status", ResourceStatus.ACTIVE.value),
                "followers_count": r.get("followers_count") or 0,
                "tags": r.get("tags", ""),
            }
            extra_metadata.append(meta)

        upsert_vectors(
            namespace=ns,
            file_id=batch_id,
            chunks=texts,
            embeddings=embeddings,
            extra_metadata=extra_metadata,
        )
        namespaces_used.append(ns)

    return {
        "imported": len(resources),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "namespaces": namespaces_used,
        "recognized_columns": parse_result.recognized_columns,
        "ignored_columns": parse_result.ignored_columns,
    }
