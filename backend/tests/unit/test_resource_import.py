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
def parse_resource_excel(file_bytes: bytes) -> list[dict]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file_bytes), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip().lower() if h else "" for h in rows[0]]
    resources = []
    for row in rows[1:]:
        if not any(row):
            continue
        record = {}
        for idx, header in enumerate(headers):
            val = row[idx] if idx < len(row) else None
            if val is not None:
                record[header] = str(val).strip()
        if record.get("name"):
            record.setdefault("type", "kol")
            record.setdefault("platform", "")
            record.setdefault("tags", "")
            resources.append(record)
    wb.close()
    return resources


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
    resources = parse_resource_excel(data)
    assert len(resources) == 2
    assert resources[0]["name"] == "Alice"
    assert resources[0]["type"] == "kol"
    assert resources[0]["platform"] == "小红书"
    assert resources[1]["name"] == "Bob"


def test_parse_skips_empty_rows():
    data = _make_xlsx([
        ["Name", "Type", "Platform"],
        ["Alice", "kol", "IG"],
        [None, None, None],
        ["Bob", "koc", "TikTok"],
    ])
    resources = parse_resource_excel(data)
    assert len(resources) == 2


def test_parse_defaults_type_to_kol():
    data = _make_xlsx([
        ["Name", "Platform"],
        ["Charlie", "YouTube"],
    ])
    resources = parse_resource_excel(data)
    assert resources[0]["type"] == "kol"


def test_parse_empty_file():
    data = _make_xlsx([])
    resources = parse_resource_excel(data)
    assert resources == []


def test_resource_to_text():
    r = {"name": "Alice", "type": "kol", "platform": "小红书", "followers": "500k", "tags": "美妆"}
    text = _resource_to_text(r)
    assert "Alice" in text
    assert "小红书" in text
    assert "500k" in text
