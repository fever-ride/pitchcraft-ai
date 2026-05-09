"""Tests for resource Excel parsing logic (inlined to avoid motor dependency)."""
import io
import pytest

openpyxl = pytest.importorskip("openpyxl")
from openpyxl import Workbook


def _make_xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# Inlined from backend.core.rag.resource_import to avoid motor import chain
KNOWN_COLUMNS = {
    "name", "type", "platform", "followers", "categories", "content_style",
    "audience_tags", "past_cpe", "tags", "pricing", "notes",
    "outlet_type", "beat", "service_type", "region",
    "placement_type", "location", "audience_reach",
}

HEADER_ALIASES = {
    "姓名": "name", "名称": "name", "资源名称": "name",
    "类型": "type", "平台": "platform",
    "粉丝数": "followers", "粉丝": "followers",
    "品类": "categories", "擅长品类": "categories",
    "内容风格": "content_style", "风格": "content_style",
    "受众": "audience_tags", "受众标签": "audience_tags",
    "历史cpe": "past_cpe", "cpe": "past_cpe",
    "标签": "tags", "报价": "pricing", "价格": "pricing", "备注": "notes",
    "媒体类型": "outlet_type", "跑线": "beat", "领域": "beat",
    "服务类型": "service_type", "区域": "region", "地区": "region",
    "广告类型": "placement_type", "位置": "location", "覆盖人群": "audience_reach",
}


class ImportParseResult:
    def __init__(self, resources, recognized, ignored):
        self.resources = resources
        self.recognized_columns = recognized
        self.ignored_columns = ignored


def parse_resource_excel(file_bytes: bytes) -> ImportParseResult:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file_bytes), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.close()
        return ImportParseResult([], [], [])

    raw_headers = [str(h).strip() if h else "" for h in rows[0]]
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
            for list_field in ("categories", "audience_tags", "tags"):
                val = record.get(list_field, "")
                if isinstance(val, str):
                    record[list_field] = [t.strip() for t in val.split(",") if t.strip()]
            resources.append(record)
    wb.close()
    return ImportParseResult(resources, recognized, ignored)


def _resource_to_text(r: dict) -> str:
    parts = [
        f"Name: {r.get('name', '')}",
        f"Type: {r.get('type', '')}",
        f"Platform: {r.get('platform', '')}",
    ]
    if r.get("followers"):
        parts.append(f"Followers: {r['followers']}")
    if r.get("tags"):
        parts.append(f"Tags: {r['tags']}")
    if r.get("pricing"):
        parts.append(f"Pricing: {r['pricing']}")
    if r.get("notes"):
        parts.append(f"Notes: {r['notes']}")
    return " | ".join(parts)


def test_parse_basic_rows():
    data = _make_xlsx([
        ["Name", "Type", "Platform", "Followers", "Tags", "Pricing", "Notes"],
        ["Alice", "kol", "小红书", "500000", "美妆,护肤", "5万/条", "Top tier"],
        ["Bob", "koc", "抖音", "50000", "生活方式", "5千/条", ""],
    ])
    result = parse_resource_excel(data)
    assert len(result.resources) == 2
    assert result.resources[0]["name"] == "Alice"
    assert result.resources[0]["type"] == "kol"
    assert result.resources[0]["platform"] == "小红书"
    assert result.resources[1]["name"] == "Bob"


def test_parse_skips_empty_rows():
    data = _make_xlsx([
        ["Name", "Type", "Platform"],
        ["Alice", "kol", "IG"],
        [None, None, None],
        ["Bob", "koc", "TikTok"],
    ])
    result = parse_resource_excel(data)
    assert len(result.resources) == 2


def test_parse_defaults_type_to_kol():
    data = _make_xlsx([
        ["Name", "Platform"],
        ["Charlie", "YouTube"],
    ])
    result = parse_resource_excel(data)
    assert result.resources[0]["type"] == "kol"


def test_parse_empty_file():
    data = _make_xlsx([])
    result = parse_resource_excel(data)
    assert result.resources == []


def test_column_recognition_english():
    data = _make_xlsx([
        ["Name", "Type", "Platform", "WeirdColumn", "Budget"],
        ["Alice", "kol", "IG", "foo", "100k"],
    ])
    result = parse_resource_excel(data)
    assert "Name" in result.recognized_columns
    assert "Type" in result.recognized_columns
    assert "Platform" in result.recognized_columns
    assert "WeirdColumn" in result.ignored_columns
    assert "Budget" in result.ignored_columns


def test_column_recognition_chinese_aliases():
    data = _make_xlsx([
        ["姓名", "平台", "粉丝数", "品类", "不认识的列"],
        ["Alice", "小红书", "50万", "美妆,护肤", "whatever"],
    ])
    result = parse_resource_excel(data)
    assert len(result.resources) == 1
    assert result.resources[0]["name"] == "Alice"
    assert result.resources[0]["platform"] == "小红书"
    assert result.resources[0]["followers"] == "50万"
    assert result.resources[0]["categories"] == ["美妆", "护肤"]
    assert "姓名" in result.recognized_columns
    assert "平台" in result.recognized_columns
    assert "粉丝数" in result.recognized_columns
    assert "品类" in result.recognized_columns
    assert "不认识的列" in result.ignored_columns


def test_column_recognition_mixed():
    data = _make_xlsx([
        ["Name", "报价", "UnknownA", "受众标签"],
        ["Bob", "5000", "x", "Z世代,女性"],
    ])
    result = parse_resource_excel(data)
    assert set(result.recognized_columns) == {"Name", "报价", "受众标签"}
    assert result.ignored_columns == ["UnknownA"]
    assert result.resources[0]["pricing"] == "5000"
    assert result.resources[0]["audience_tags"] == ["Z世代", "女性"]


def test_resource_to_text():
    r = {"name": "Alice", "type": "kol", "platform": "小红书", "followers": "500k", "tags": "美妆"}
    text = _resource_to_text(r)
    assert "Alice" in text
    assert "小红书" in text
    assert "500k" in text


def test_alias_case_insensitive():
    """Header alias matching should be case-insensitive."""
    data = _make_xlsx([
        ["姓名", "PLATFORM", "Followers"],
        ["Eve", "IG", "10k"],
    ])
    result = parse_resource_excel(data)
    assert len(result.resources) == 1
    assert result.resources[0]["name"] == "Eve"
    assert result.resources[0]["platform"] == "IG"
    assert result.resources[0]["followers"] == "10k"


def test_all_ignored_columns():
    """File with no recognized columns still returns empty resources."""
    data = _make_xlsx([
        ["Foo", "Bar", "Baz"],
        ["a", "b", "c"],
    ])
    result = parse_resource_excel(data)
    assert result.resources == []
    assert set(result.ignored_columns) == {"Foo", "Bar", "Baz"}
    assert result.recognized_columns == []


def test_list_normalization_in_parse():
    """categories and audience_tags are split from comma-separated string to list."""
    data = _make_xlsx([
        ["Name", "Categories", "Audience_tags", "Tags"],
        ["Frank", "美妆,护肤,彩妆", "Z世代,女性", "头部,种草"],
    ])
    result = parse_resource_excel(data)
    r = result.resources[0]
    assert r["categories"] == ["美妆", "护肤", "彩妆"]
    assert r["audience_tags"] == ["Z世代", "女性"]
    assert r["tags"] == ["头部", "种草"]


def test_empty_list_fields_default():
    """Empty categories/audience_tags default to empty list."""
    data = _make_xlsx([
        ["Name", "Type"],
        ["Grace", "media"],
    ])
    result = parse_resource_excel(data)
    r = result.resources[0]
    assert r["categories"] == []
    assert r["audience_tags"] == []
    assert r["tags"] == []
