"""Render PPTX/PDF files to per-page PNG images using LibreOffice headless."""
import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


async def render_to_pngs(file_bytes: bytes, filename: str, output_dir: str) -> list[str]:
    """Convert a PPTX or PDF to individual PNG images. Returns list of PNG file paths.

    Requires LibreOffice headless to be available (Docker sidecar or system install).
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in (".pptx", ".pdf", ".ppt"):
        return []

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    try:
        if suffix == ".pdf":
            return await _render_pdf(tmp_path, out_path)
        else:
            return await _render_pptx_via_libreoffice(tmp_path, out_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def _render_pptx_via_libreoffice(input_path: str, output_dir: Path) -> list[str]:
    """Use LibreOffice to convert PPTX → PDF → PNG pages."""
    # Step 1: PPTX → PDF
    proc = await asyncio.create_subprocess_exec(
        "libreoffice", "--headless", "--convert-to", "pdf",
        "--outdir", str(output_dir), input_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error(f"LibreOffice conversion failed: {stderr.decode()}")
        return []

    # Find the generated PDF
    pdf_name = Path(input_path).stem + ".pdf"
    pdf_path = output_dir / pdf_name
    if not pdf_path.exists():
        return []

    # Step 2: PDF → PNGs
    pngs = await _render_pdf(str(pdf_path), output_dir)
    pdf_path.unlink(missing_ok=True)
    return pngs


async def _render_pdf(pdf_path: str, output_dir: Path) -> list[str]:
    """Render PDF pages to individual PNGs using pdftoppm (poppler-utils)."""
    prefix = output_dir / "slide"

    proc = await asyncio.create_subprocess_exec(
        "pdftoppm", "-png", "-r", "150", pdf_path, str(prefix),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error(f"pdftoppm failed: {stderr.decode()}")
        return []

    # Collect generated PNGs (named like slide-01.png, slide-02.png)
    pngs = sorted(output_dir.glob("slide-*.png"))
    return [str(p) for p in pngs]


def generate_thumbnail(png_path: str, max_width: int = 400) -> bytes:
    """Generate a low-res thumbnail from a full-size PNG. Returns PNG bytes."""
    try:
        from PIL import Image
        import io

        with Image.open(png_path) as img:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue()
    except ImportError:
        # Pillow not available, return original
        return Path(png_path).read_bytes()
