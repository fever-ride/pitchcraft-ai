"""Visual style extraction: Claude Vision analysis of rendered slide PNGs."""
import base64
import json
import logging

from langchain_core.messages import HumanMessage

from backend.core.agents.llm import invoke_llm, strip_code_block

logger = logging.getLogger(__name__)

STYLE_EXTRACTION_PROMPT = """Analyze this presentation slide image and extract visual style information.

Output strictly in JSON format:
{{
  "color_palette": {{
    "primary": "#hex",
    "secondary": "#hex",
    "accent": "#hex",
    "background": "#hex"
  }},
  "layout_pattern": "description (e.g. full-bleed image, left-right split, centered title)",
  "typography": {{
    "style": "serif/sans-serif/mixed",
    "weight_hierarchy": "description",
    "size_contrast": "high/medium/low"
  }},
  "image_to_text_ratio": 0.7,
  "visual_density": "minimal/moderate/dense",
  "design_keywords": ["keyword1", "keyword2", "keyword3"],
  "notable_elements": ["icons", "charts", "illustrations", "photography"],
  "photography_style": "description or null",
  "is_mostly_text": false
}}

If the slide is >80% text content (e.g. a bullet point slide or agenda), set "is_mostly_text": true."""

SUMMARY_PROMPT = """Based on the following individual slide style analyses from a single presentation file, create a file-level Visual Identity Summary.

Slide analyses:
{analyses}

Output strictly in JSON format:
{{
  "dominant_colors": {{
    "primary": "#hex (most frequent)",
    "secondary": "#hex",
    "accent": "#hex"
  }},
  "dominant_layout": "most common layout pattern",
  "typography_system": "description of font usage patterns",
  "overall_density": "minimal/moderate/dense",
  "design_language": ["top 5 design keywords across all slides"],
  "visual_consistency_score": 0.85,
  "style_description": "2-3 sentence natural language description of the visual identity",
  "recommendations_for_new_deck": "1-2 sentences on how to maintain this style"
}}"""


async def extract_slide_style(png_path: str) -> dict:
    """Extract style from a single slide PNG using Claude Vision."""
    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    content = [
        {"type": "text", "text": STYLE_EXTRACTION_PROMPT},
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": b64,
            },
        },
    ]

    text = await invoke_llm(
        [HumanMessage(content=content)],
        temperature=0,
        max_tokens=1000,
    )
    text = strip_code_block(text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse style JSON for {png_path}")
        return {"error": "parse_failed", "raw": text[:200]}


async def extract_batch_styles(
    png_paths: list[str],
    batch_size: int = 5,
) -> list[dict]:
    """Extract styles from multiple PNGs, batched to manage API rate limits."""
    results = []
    for i in range(0, len(png_paths), batch_size):
        batch = png_paths[i:i + batch_size]
        for path in batch:
            style = await extract_slide_style(path)
            # Skip mostly-text slides
            if style.get("is_mostly_text"):
                continue
            results.append(style)
    return results


async def generate_visual_summary(slide_styles: list[dict]) -> dict:
    """Generate file-level visual identity summary from individual slide analyses."""
    if not slide_styles:
        return {"error": "no_visual_slides", "style_description": "No visual content detected."}

    analyses_text = json.dumps(slide_styles, ensure_ascii=False)[:6000]
    prompt = SUMMARY_PROMPT.format(analyses=analyses_text)

    text = await invoke_llm(
        [HumanMessage(content=prompt)],
        temperature=0,
        max_tokens=1500,
    )
    text = strip_code_block(text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "parse_failed", "raw": text[:300]}


def style_to_embedding_text(style: dict) -> str:
    """Convert a style dict to a text suitable for embedding."""
    parts = []
    if style.get("color_palette"):
        cp = style["color_palette"]
        parts.append(f"Colors: primary={cp.get('primary')}, secondary={cp.get('secondary')}, accent={cp.get('accent')}")
    if style.get("layout_pattern"):
        parts.append(f"Layout: {style['layout_pattern']}")
    if style.get("typography"):
        t = style["typography"]
        parts.append(f"Typography: {t.get('style')}, contrast={t.get('size_contrast')}")
    if style.get("visual_density"):
        parts.append(f"Density: {style['visual_density']}")
    if style.get("design_keywords"):
        parts.append(f"Keywords: {', '.join(style['design_keywords'])}")
    if style.get("notable_elements"):
        parts.append(f"Elements: {', '.join(style['notable_elements'])}")
    if style.get("photography_style"):
        parts.append(f"Photography: {style['photography_style']}")
    return " | ".join(parts)


def summary_to_embedding_text(summary: dict) -> str:
    """Convert visual identity summary to text for embedding."""
    parts = [
        "[Visual Identity Summary]",
        f"Style: {summary.get('style_description', '')}",
        f"Design language: {', '.join(summary.get('design_language', []))}",
        f"Layout: {summary.get('dominant_layout', '')}",
        f"Typography: {summary.get('typography_system', '')}",
        f"Density: {summary.get('overall_density', '')}",
    ]
    if summary.get("recommendations_for_new_deck"):
        parts.append(f"Recommendations: {summary['recommendations_for_new_deck']}")
    return " | ".join(parts)
