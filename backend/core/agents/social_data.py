"""Social data API connectors for competitor analysis.

Supports:
- Chanmama (蝉妈妈) — Douyin/TikTok analytics (China)
- Feigua (飞瓜) — Xiaohongshu/Douyin analytics (China)
- CreatorIQ — Global influencer analytics

All connectors return a unified format for downstream consumption.
"""
import httpx

from backend.core.config import settings
from backend.core.stability.fallback import FallbackChain


class SocialDataResult:
    def __init__(
        self,
        platform: str,
        account_name: str,
        followers: int | None = None,
        engagement_rate: float | None = None,
        avg_likes: int | None = None,
        avg_comments: int | None = None,
        content_frequency: str | None = None,
        top_content_themes: list[str] | None = None,
        audience_demographics: dict | None = None,
        raw_data: dict | None = None,
    ):
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

    def to_dict(self) -> dict:
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

    def to_text(self) -> str:
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


async def _query_chanmama(keyword: str) -> list[SocialDataResult]:
    """Query Chanmama API for Douyin account data."""
    api_key = getattr(settings, "chanmama_api_key", "")
    if not api_key:
        return []

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.chanmama.com/v1/search/author",
            params={"keyword": keyword, "limit": 5},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()

    results = []
    for item in data.get("data", {}).get("list", []):
        results.append(SocialDataResult(
            platform="douyin",
            account_name=item.get("nickname", ""),
            followers=item.get("follower_count"),
            engagement_rate=item.get("interaction_rate"),
            avg_likes=item.get("avg_digg_count"),
            top_content_themes=item.get("tags", []),
            raw_data=item,
        ))
    return results


async def _query_feigua(keyword: str) -> list[SocialDataResult]:
    """Query Feigua API for Xiaohongshu data."""
    api_key = getattr(settings, "feigua_api_key", "")
    if not api_key:
        return []

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.feigua.cn/v1/xhs/search/blogger",
            params={"keyword": keyword, "limit": 5},
            headers={"X-API-Key": api_key},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()

    results = []
    for item in data.get("data", []):
        results.append(SocialDataResult(
            platform="xiaohongshu",
            account_name=item.get("name", ""),
            followers=item.get("fans_count"),
            engagement_rate=item.get("engagement_rate"),
            avg_likes=item.get("avg_likes"),
            avg_comments=item.get("avg_comments"),
            top_content_themes=item.get("categories", []),
            raw_data=item,
        ))
    return results


async def _query_creatoriq(keyword: str) -> list[SocialDataResult]:
    """Query CreatorIQ for global influencer data."""
    api_key = getattr(settings, "creatoriq_api_key", "")
    if not api_key:
        return []

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.creatoriq.com/v2/creators/search",
            json={"query": keyword, "limit": 5},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()

    results = []
    for item in data.get("creators", []):
        results.append(SocialDataResult(
            platform=item.get("primary_platform", "instagram"),
            account_name=item.get("username", ""),
            followers=item.get("follower_count"),
            engagement_rate=item.get("engagement_rate"),
            avg_likes=item.get("avg_likes"),
            top_content_themes=item.get("content_categories", []),
            audience_demographics=item.get("demographics", {}),
            raw_data=item,
        ))
    return results


async def fetch_social_data(keyword: str, locale: str = "global") -> list[SocialDataResult]:
    """Fetch social data with locale-aware source selection and fallback."""
    if locale == "cn":
        chain = FallbackChain(service_name="social_data_cn")
        results, _ = await chain.execute(
            primary_fn=lambda: _query_chanmama(keyword),
            secondary_fn=lambda: _query_feigua(keyword),
            fallback_fn=lambda: [],
        )
    else:
        chain = FallbackChain(service_name="social_data_global")
        results, _ = await chain.execute(
            primary_fn=lambda: _query_creatoriq(keyword),
            secondary_fn=lambda: [],
            fallback_fn=lambda: [],
        )

    return results or []
