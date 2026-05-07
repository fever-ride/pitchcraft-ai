import pytest

from backend.core.rag.chunker import count_tokens, semantic_chunk


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
