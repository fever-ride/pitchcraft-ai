from enum import Enum
from functools import wraps

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.core.config import settings

security = HTTPBearer()


class Role(str, Enum):
    ACCOUNT = "account"
    LEAD_ACCOUNT = "lead_account"
    ADMIN = "admin"


ROLE_HIERARCHY = {
    Role.ACCOUNT: 0,
    Role.LEAD_ACCOUNT: 1,
    Role.ADMIN: 2,
}


class CurrentUser:
    def __init__(self, user_id: str, organization_id: str, role: Role):
        self.user_id = user_id
        self.organization_id = organization_id
        self.role = role


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id = payload.get("sub")
        organization_id = payload.get("org_id")
        role = payload.get("role")
        if not user_id or not organization_id or not role:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return CurrentUser(
            user_id=user_id,
            organization_id=organization_id,
            role=Role(role),
        )
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


def require_role(minimum_role: Role):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: CurrentUser = Depends(get_current_user), **kwargs):
            if ROLE_HIERARCHY[user.role] < ROLE_HIERARCHY[minimum_role]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires {minimum_role.value} role or above",
                )
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator
