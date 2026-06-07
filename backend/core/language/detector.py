from langdetect import detect


def detect_language(text: str) -> str:
    """Detect whether text is primarily Chinese ('zh') or English ('en').

    Uses CJK character proportion as the primary signal before falling back
    to langdetect. This prevents misclassification of Chinese text that
    contains many English loan words (KPI, ROI, platform names, etc.).
    """
    # Count CJK characters (BMP + Extension A range)
    cjk_count = sum(
        1 for c in text
        if "一" <= c <= "鿿" or "㐀" <= c <= "䶿"
    )
    alpha_count = sum(1 for c in text if c.isalpha())
    if alpha_count > 0 and cjk_count / alpha_count > 0.25:
        return "zh"

    # Fall back to langdetect for non-CJK-dominant text
    try:
        lang = detect(text)
        if lang.startswith("zh"):
            return "zh"
        elif lang == "en":
            return "en"
        else:
            return "en"
    except Exception:
        return "en"


def resolve_output_language(output_language: str, fallback_text: str) -> str:
    """Resolve the actual output language.

    If user set "zh" or "en" explicitly, use that.
    If "auto" (default), detect from fallback_text.
    """
    if output_language in ("zh", "en"):
        return output_language
    return detect_language(fallback_text)
