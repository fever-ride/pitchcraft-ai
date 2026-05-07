import io

import pytest

pypdf = pytest.importorskip("pypdf")
docx = pytest.importorskip("docx")
pptx = pytest.importorskip("pptx")

from backend.core.rag.parser import parse_file


def test_parse_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_file(b"content", "file.txt")


def test_parse_pdf_empty():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)

    result = parse_file(buf.read(), "test.pdf")
    assert result == ""


def test_parse_docx():
    from docx import Document

    doc = Document()
    doc.add_paragraph("Hello world")
    doc.add_paragraph("Second paragraph")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    result = parse_file(buf.read(), "test.docx")
    assert "Hello world" in result
    assert "Second paragraph" in result


def test_parse_pptx():
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Test Title"
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)

    result = parse_file(buf.read(), "deck.pptx")
    assert "Test Title" in result
    assert "[Slide 1]" in result
