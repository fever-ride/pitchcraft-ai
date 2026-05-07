import re

import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")

DEFAULT_MAX_TOKENS = 512
DEFAULT_OVERLAP_TOKENS = 64


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _split_into_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def _split_into_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    return [s.strip() for s in parts if s.strip()]


def semantic_chunk(
    text: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[str]:
    """Token-based chunking that respects paragraph and sentence boundaries."""
    paragraphs = _split_into_paragraphs(text)

    chunks: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)

        if para_tokens > max_tokens:
            if current_parts:
                chunks.append("\n\n".join(current_parts))
                current_parts = []
                current_tokens = 0

            sentences = _split_into_sentences(para)
            sent_parts: list[str] = []
            sent_tokens = 0

            for sent in sentences:
                st = count_tokens(sent)
                if sent_tokens + st > max_tokens and sent_parts:
                    chunks.append(" ".join(sent_parts))
                    overlap_text = _get_overlap(sent_parts, overlap_tokens)
                    sent_parts = [overlap_text, sent] if overlap_text else [sent]
                    sent_tokens = count_tokens(" ".join(sent_parts))
                else:
                    sent_parts.append(sent)
                    sent_tokens += st

            if sent_parts:
                chunks.append(" ".join(sent_parts))
            continue

        if current_tokens + para_tokens > max_tokens and current_parts:
            chunks.append("\n\n".join(current_parts))
            overlap_text = _get_overlap(current_parts, overlap_tokens)
            current_parts = [overlap_text] if overlap_text else []
            current_tokens = count_tokens(overlap_text) if overlap_text else 0

        current_parts.append(para)
        current_tokens += para_tokens

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return chunks


def _get_overlap(parts: list[str], overlap_tokens: int) -> str:
    """Take trailing text from parts that fits within overlap_tokens."""
    combined = " ".join(parts)
    tokens = _enc.encode(combined)
    if len(tokens) <= overlap_tokens:
        return combined
    overlap = _enc.decode(tokens[-overlap_tokens:])
    return overlap.strip()
