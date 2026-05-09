from langdetect import detect


def detect_language(text: str) -> str:
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
