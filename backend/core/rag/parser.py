import io
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedSegment:
    """A segment of text from a parsed document with source location metadata."""
    text: str
    page_number: int | None = None
    slide_index: int | None = None


@dataclass
class ParsedDocument:
    """Full parsed output with metadata for downstream contextual embedding."""
    segments: list[ParsedSegment] = field(default_factory=list)
    total_pages: int = 0

    @property
    def full_text(self) -> str:
        return "\n\n".join(seg.text for seg in self.segments if seg.text.strip())


def parse_pdf(file_bytes: bytes) -> ParsedDocument:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    segments = []
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text and text.strip():
            segments.append(ParsedSegment(text=text.strip(), page_number=i))
    return ParsedDocument(segments=segments, total_pages=len(reader.pages))


def parse_docx(file_bytes: bytes) -> ParsedDocument:
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    full_text = "\n\n".join(paragraphs)
    segments = [ParsedSegment(text=full_text, page_number=None)]
    return ParsedDocument(segments=segments, total_pages=1)


def parse_pptx(file_bytes: bytes) -> ParsedDocument:
    from pptx import Presentation

    prs = Presentation(io.BytesIO(file_bytes))
    segments = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        texts.append(text)
        if texts:
            segments.append(ParsedSegment(text="\n".join(texts), slide_index=i))
    return ParsedDocument(segments=segments, total_pages=len(prs.slides))


def parse_file(file_bytes: bytes, filename: str) -> str:
    """Legacy interface: returns plain text with location markers.

    Use parse_file_structured() for the new pipeline with metadata tracking.
    """
    doc = parse_file_structured(file_bytes, filename)
    parts = []
    for seg in doc.segments:
        if not seg.text.strip():
            continue
        if seg.slide_index is not None:
            parts.append(f"[Slide {seg.slide_index}]\n{seg.text}")
        else:
            parts.append(seg.text)
    return "\n\n".join(parts)


def parse_file_structured(file_bytes: bytes, filename: str) -> ParsedDocument:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return parse_pdf(file_bytes)
    elif ext == ".docx":
        return parse_docx(file_bytes)
    elif ext in (".pptx", ".ppt"):
        return parse_pptx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
