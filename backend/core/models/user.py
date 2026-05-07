from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    ACCOUNT = "account"
    LEAD_ACCOUNT = "lead_account"
    ADMIN = "admin"


class User(BaseModel):
    id: str | None = Field(None, alias="_id")
    organization_id: str
    name: str
    email: EmailStr
    password_hash: str | None = None
    oauth_provider: str | None = None
    oauth_id: str | None = None
    role: UserRole = UserRole.ACCOUNT
    created_at: datetime = Field(default_factory=datetime.utcnow)
