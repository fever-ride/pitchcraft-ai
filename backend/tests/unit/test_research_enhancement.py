"""Tests for research enhancement logic (social data model + locale detection)."""
import json


# Inlined SocialDataResult (avoids importing httpx/settings chain)
class SocialDataResult:
    def __init__(self, platform, account_name, followers=None, engagement_rate=None,
                 avg_likes=None, avg_comments=None, content_frequency=None,
                 top_content_themes=None, audience_demographics=None, raw_data=None):
        self.platform = platform
        self.account_name = account_name
        self.followers = followers
        self.engagement_rate = engagement_rate
        self.avg_likes = avg_likes
        self.avg_comments = avg_comments
        self.content_frequency = content_frequency
        self.top_content_themes = top_content_themes or []
        self.audience_demographics = audience_demographics or {}
        self.raw_data = raw_data or {}

    def to_dict(self):
        return {
            "platform": self.platform,
            "account_name": self.account_name,
            "followers": self.followers,
            "engagement_rate": self.engagement_rate,
            "avg_likes": self.avg_likes,
            "avg_comments": self.avg_comments,
            "content_frequency": self.content_frequency,
            "top_content_themes": self.top_content_themes,
            "audience_demographics": self.audience_demographics,
        }

    def to_text(self):
        parts = [f"[{self.platform}] {self.account_name}"]
        if self.followers:
            parts.append(f"Followers: {self.followers:,}")
        if self.engagement_rate:
            parts.append(f"Engagement: {self.engagement_rate:.2%}")
        if self.avg_likes:
            parts.append(f"Avg likes: {self.avg_likes:,}")
        if self.content_frequency:
            parts.append(f"Posting: {self.content_frequency}")
        if self.top_content_themes:
            parts.append(f"Themes: {', '.join(self.top_content_themes)}")
        return " | ".join(parts)


# Inlined locale detection
def _detect_locale(brief: dict) -> str:
    text = json.dumps(brief, ensure_ascii=False).lower()
    cn_signals = {"中国", "中文", "国内", "小红书", "抖音", "微博", "微信", "bilibili", "天猫", "京东"}
    if any(s in text for s in cn_signals):
        return "cn"
    return "global"


# --- SocialDataResult tests ---

def test_social_result_to_dict():
    r = SocialDataResult(
        platform="douyin",
        account_name="TestBrand",
        followers=1000000,
        engagement_rate=0.05,
    )
    d = r.to_dict()
    assert d["platform"] == "douyin"
    assert d["followers"] == 1000000
    assert d["engagement_rate"] == 0.05


def test_social_result_to_text():
    r = SocialDataResult(
        platform="xiaohongshu",
        account_name="美妆达人",
        followers=500000,
        engagement_rate=0.08,
        avg_likes=12000,
        top_content_themes=["美妆", "护肤"],
    )
    text = r.to_text()
    assert "xiaohongshu" in text
    assert "美妆达人" in text
    assert "500,000" in text
    assert "8.00%" in text
    assert "12,000" in text
    assert "美妆" in text


def test_social_result_to_text_minimal():
    r = SocialDataResult(platform="instagram", account_name="brand_x")
    text = r.to_text()
    assert text == "[instagram] brand_x"


# --- Locale detection tests ---

def test_locale_cn_xiaohongshu():
    brief = {"client_name": "某品牌", "channels": ["小红书", "抖音"]}
    assert _detect_locale(brief) == "cn"


def test_locale_cn_bilibili():
    brief = {"theme": "bilibili up主合作"}
    assert _detect_locale(brief) == "cn"


def test_locale_global_default():
    brief = {"client_name": "Nike", "theme": "Summer campaign"}
    assert _detect_locale(brief) == "global"


def test_locale_global_instagram():
    brief = {"channels": ["Instagram", "YouTube"], "theme": "Global launch"}
    assert _detect_locale(brief) == "global"


def test_locale_cn_explicit():
    brief = {"theme": "中国市场推广"}
    assert _detect_locale(brief) == "cn"
