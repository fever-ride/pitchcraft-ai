"""Visual competitor analysis: analyze uploaded screenshots via Claude Vision."""
import base64
import json

from langchain_core.messages import HumanMessage

from backend.core.agents.llm import invoke_llm, strip_code_block
from backend.core.graph.state import RequestBudget

VISUAL_ANALYSIS_PROMPT = {
    "zh": """分析这张竞品社交媒体/广告截图，提取以下信息：

输出JSON格式：
{{
  "brand": "品牌名（如可识别）",
  "platform": "平台（如可识别）",
  "content_type": "图文/视频封面/banner/信息流广告/故事",
  "visual_style": {{
    "color_palette": ["主色", "辅色"],
    "layout": "布局描述",
    "typography": "字体风格",
    "imagery": "图片/插画风格"
  }},
  "messaging": {{
    "headline": "主标题（如有）",
    "tone": "语气风格",
    "cta": "行动号召（如有）"
  }},
  "engagement_indicators": {{
    "likes": "数量或null",
    "comments": "数量或null",
    "shares": "数量或null"
  }},
  "strategic_takeaway": "对我们campaign的启示（1-2句）"
}}""",

    "en": """Analyze this competitor social media/ad screenshot and extract the following:

Output in JSON format:
{{
  "brand": "brand name (if identifiable)",
  "platform": "platform (if identifiable)",
  "content_type": "post/video_cover/banner/feed_ad/story",
  "visual_style": {{
    "color_palette": ["primary", "secondary"],
    "layout": "layout description",
    "typography": "font style",
    "imagery": "photo/illustration style"
  }},
  "messaging": {{
    "headline": "main headline (if any)",
    "tone": "tone of voice",
    "cta": "call to action (if any)"
  }},
  "engagement_indicators": {{
    "likes": "count or null",
    "comments": "count or null",
    "shares": "count or null"
  }},
  "strategic_takeaway": "insight for our campaign (1-2 sentences)"
}}""",
}


async def analyze_competitor_screenshot(
    image_bytes: bytes,
    mime_type: str = "image/png",
    lang: str = "en",
    budget: RequestBudget | None = None,
) -> dict:
    """Analyze a single competitor screenshot using Claude Vision."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    content = [
        {"type": "text", "text": VISUAL_ANALYSIS_PROMPT[lang]},
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": b64,
            },
        },
    ]

    text = await invoke_llm(
        [HumanMessage(content=content)],
        budget=budget,
        temperature=0,
        max_tokens=1500,
    )
    text = strip_code_block(text)
    return json.loads(text)


async def analyze_competitor_batch(
    images: list[tuple[bytes, str]],
    lang: str = "en",
    budget: RequestBudget | None = None,
) -> list[dict]:
    """Analyze multiple competitor screenshots. Returns list of analysis results."""
    results = []
    for image_bytes, mime_type in images:
        result = await analyze_competitor_screenshot(image_bytes, mime_type, lang, budget)
        results.append(result)
    return results
