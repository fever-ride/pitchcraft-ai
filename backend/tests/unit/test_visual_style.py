"""Tests for visual style embedding text conversion (no external deps)."""


# Inlined from backend.core.rag.visual_style
def style_to_embedding_text(style: dict) -> str:
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
    parts = [
        f"[Visual Identity Summary]",
        f"Style: {summary.get('style_description', '')}",
        f"Design language: {', '.join(summary.get('design_language', []))}",
        f"Layout: {summary.get('dominant_layout', '')}",
        f"Typography: {summary.get('typography_system', '')}",
        f"Density: {summary.get('overall_density', '')}",
    ]
    if summary.get("recommendations_for_new_deck"):
        parts.append(f"Recommendations: {summary['recommendations_for_new_deck']}")
    return " | ".join(parts)


def test_style_to_text_full():
    style = {
        "color_palette": {"primary": "#1A1A2E", "secondary": "#E94D6A", "accent": "#00B4D8", "background": "#FFFFFF"},
        "layout_pattern": "left-right split",
        "typography": {"style": "sans-serif", "weight_hierarchy": "bold title, regular body", "size_contrast": "high"},
        "visual_density": "moderate",
        "design_keywords": ["modern", "clean", "tech-forward"],
        "notable_elements": ["icons", "charts"],
        "photography_style": "lifestyle editorial",
    }
    text = style_to_embedding_text(style)
    assert "#1A1A2E" in text
    assert "left-right split" in text
    assert "sans-serif" in text
    assert "moderate" in text
    assert "modern" in text
    assert "icons" in text
    assert "lifestyle editorial" in text


def test_style_to_text_minimal():
    style = {"layout_pattern": "full-bleed image"}
    text = style_to_embedding_text(style)
    assert text == "Layout: full-bleed image"


def test_style_to_text_empty():
    text = style_to_embedding_text({})
    assert text == ""


def test_summary_to_text():
    summary = {
        "dominant_colors": {"primary": "#333", "secondary": "#666", "accent": "#FF0000"},
        "dominant_layout": "centered title + subtitle",
        "typography_system": "Helvetica Neue, bold headers",
        "overall_density": "minimal",
        "design_language": ["corporate", "premium", "clean"],
        "visual_consistency_score": 0.9,
        "style_description": "Clean corporate design with bold typography and minimal imagery.",
        "recommendations_for_new_deck": "Use dark backgrounds with white text for impact.",
    }
    text = summary_to_embedding_text(summary)
    assert "[Visual Identity Summary]" in text
    assert "Clean corporate" in text
    assert "corporate" in text
    assert "centered title" in text
    assert "Helvetica" in text
    assert "minimal" in text
    assert "dark backgrounds" in text


def test_summary_to_text_no_recommendations():
    summary = {
        "style_description": "Playful design",
        "design_language": ["fun"],
        "dominant_layout": "grid",
        "typography_system": "rounded",
        "overall_density": "dense",
    }
    text = summary_to_embedding_text(summary)
    assert "Recommendations" not in text
    assert "Playful design" in text
