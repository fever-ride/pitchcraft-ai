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
