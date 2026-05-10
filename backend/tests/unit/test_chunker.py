import pytest

from backend.core.rag.chunker import (
    CHUNK_PROFILES,
    count_tokens,
    semantic_chunk,
    semantic_chunk_with_metadata,
)
from backend.core.rag.parser import ParsedSegment


def test_count_tokens_basic():
    assert count_tokens("hello world") > 0


def test_single_short_paragraph_no_split():
    text = "This is a short paragraph."
    chunks = semantic_chunk(text, max_tokens=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_multiple_paragraphs_within_limit():
    text = "First paragraph.\n\nSecond paragraph."
    chunks = semantic_chunk(text, max_tokens=100)
    assert len(chunks) == 1
    assert "First paragraph." in chunks[0]
    assert "Second paragraph." in chunks[0]


def test_paragraphs_exceed_limit_creates_multiple_chunks():
    para = "Word " * 100
    text = f"{para}\n\n{para}\n\n{para}"
    chunks = semantic_chunk(text, max_tokens=150, overlap_tokens=20)
    assert len(chunks) > 1


def test_long_paragraph_split_by_sentences():
    sentences = ["This is sentence number %d." % i for i in range(50)]
    text = " ".join(sentences)
    chunks = semantic_chunk(text, max_tokens=50, overlap_tokens=10)
    assert len(chunks) > 1
    for chunk in chunks:
        assert count_tokens(chunk) <= 60  # allow small overflow from overlap


def test_empty_text():
    chunks = semantic_chunk("")
    assert chunks == []


def test_chinese_text():
    text = "这是第一段。\n\n这是第二段，包含更多的中文内容。"
    chunks = semantic_chunk(text, max_tokens=100)
    assert len(chunks) >= 1
    assert "第一段" in chunks[0]


# --- Adaptive chunking with metadata ---


def test_chunk_profiles_exist_for_brand_spec():
    assert "brand_spec" in CHUNK_PROFILES
    max_tokens, overlap = CHUNK_PROFILES["brand_spec"]
    assert max_tokens == 800
    assert overlap == 200


def test_semantic_chunk_with_metadata_preserves_page_number():
    segments = [
        ParsedSegment(text="Short text on page one.", page_number=1),
        ParsedSegment(text="Another paragraph on page two.", page_number=2),
    ]
    results = semantic_chunk_with_metadata(segments, file_type="brand_spec")
    assert len(results) >= 1
    assert results[0].page_number == 1
    assert results[0].text == "Short text on page one."


def test_semantic_chunk_with_metadata_preserves_slide_index():
    segments = [
        ParsedSegment(text="Slide content here.", slide_index=3),
    ]
    results = semantic_chunk_with_metadata(segments, file_type=None)
    assert results[0].slide_index == 3


def test_semantic_chunk_with_metadata_uses_default_for_unknown_type():
    long_text = "This is a moderately long sentence for testing purposes. " * 200
    segments = [ParsedSegment(text=long_text, page_number=1)]
    results = semantic_chunk_with_metadata(segments, file_type="unknown_type")
    assert len(results) > 1
    for r in results:
        assert r.page_number == 1


def test_semantic_chunk_with_metadata_skips_empty_segments():
    segments = [
        ParsedSegment(text="", page_number=1),
        ParsedSegment(text="   ", page_number=2),
        ParsedSegment(text="Real content.", page_number=3),
    ]
    results = semantic_chunk_with_metadata(segments)
    assert len(results) == 1
    assert results[0].page_number == 3
