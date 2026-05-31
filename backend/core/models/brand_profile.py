from datetime import datetime
from pydantic import BaseModel, Field


class BrandProfile(BaseModel):
    id: str | None = Field(None, alias="_id")
    client_id: str
    org_id: str
    brand_name: str | None = None
    positioning: str | None = None        # What the brand stands for, for whom, vs whom
    personality: list[str] = []           # e.g. ["权威", "亲民", "专业"]
    target_audience: str | None = None    # Who they talk to
    usage_scenes: list[str] = []          # When/where consumers use the brand (生活/情绪/社交场景)
    user_pain_points: list[str] = []      # What problems the brand solves for users
    rtb: list[str] = []                   # Reason to Believe — credibility evidence (tech, awards, ingredients, heritage)
    tone_principles: list[str] = []       # e.g. ["直接有力", "避免娱乐化表达"]
    forbidden_directions: list[str] = []  # What to never do
    key_messages: list[str] = []          # Core messages the brand wants to convey
    competitive_position: str | None = None  # How they differentiate
    # Dynamic fields — populated from feedback loop, not from document upload
    approved_directions: list[str] = []
    rejected_directions: list[str] = []
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
