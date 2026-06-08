from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

from backend.core.config import settings
from backend.core.database.connection import get_database
from backend.core.database.repositories.users import UserRepository

router = APIRouter()


def _verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def _hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


def _create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + expires_delta
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _create_token_pair(user: dict) -> TokenResponse:
    access_token = _create_token(
        {
            "sub": str(user["_id"]),
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "org_id": user.get("organization_id", ""),
            "role": user.get("role", "user"),
        },
        timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    refresh_token = _create_token(
        {"sub": str(user["_id"]), "type": "refresh"},
        timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    db = await get_database()
    repo = UserRepository(db)
    user = await repo.find_by_email(request.email)

    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not _verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return _create_token_pair(user)


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    db = await get_database()
    repo = UserRepository(db)
    existing = await repo.find_by_email(request.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = _hash_password(request.password)
    user_id = await repo.create({
        "email": request.email,
        "name": request.name or request.email.split("@")[0],
        "password_hash": hashed,
        "role": "user",
        "organization_id": "",
        "created_at": datetime.now(timezone.utc),
    })
    user = await repo.get_by_id(user_id)
    return _create_token_pair(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    try:
        payload = jwt.decode(
            request.refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = payload.get("sub")
        db = await get_database()
        repo = UserRepository(db)
        user = await repo.get_by_id(user_id)

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return _create_token_pair(user)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/google")
async def google_oauth_redirect():
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": f"{settings.oauth_redirect_base_url}/api/v1/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


@router.get("/google/callback")
async def google_oauth_callback(code: str):
    import httpx

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": f"{settings.oauth_redirect_base_url}/api/v1/auth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")

        tokens = token_resp.json()
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo = userinfo_resp.json()

    db = await get_database()
    repo = UserRepository(db)
    user = await repo.find_by_oauth("google", userinfo["id"])

    if not user:
        user = await repo.find_by_email(userinfo["email"])
        if user:
            await repo.update(str(user["_id"]), {
                "oauth_provider": "google",
                "oauth_id": userinfo["id"],
            })
        else:
            # TODO: new OAuth users need org binding flow (invite link or manual assignment)
            user_id = await repo.create({
                "email": userinfo["email"],
                "name": userinfo.get("name", ""),
                "oauth_provider": "google",
                "oauth_id": userinfo["id"],
                "organization_id": "",
                "role": "account",
                "created_at": datetime.utcnow(),
            })
            user = await repo.get_by_id(user_id)

    token_pair = _create_token_pair(user)
    redirect_url = f"{settings.oauth_redirect_base_url}/login?token={token_pair.access_token}&refresh={token_pair.refresh_token}"
    return RedirectResponse(redirect_url)


@router.get("/microsoft")
async def microsoft_oauth_redirect():
    params = {
        "client_id": settings.microsoft_client_id,
        "redirect_uri": f"{settings.oauth_redirect_base_url}/api/v1/auth/microsoft/callback",
        "response_type": "code",
        "scope": "openid email profile",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(
        f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{query}"
    )


@router.get("/microsoft/callback")
async def microsoft_oauth_callback(code: str):
    import httpx

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "code": code,
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "redirect_uri": f"{settings.oauth_redirect_base_url}/api/v1/auth/microsoft/callback",
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")

        tokens = token_resp.json()
        userinfo_resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo = userinfo_resp.json()

    db = await get_database()
    repo = UserRepository(db)
    ms_id = userinfo.get("id", "")
    user = await repo.find_by_oauth("microsoft", ms_id)

    if not user:
        email = userinfo.get("mail") or userinfo.get("userPrincipalName", "")
        user = await repo.find_by_email(email)
        if user:
            await repo.update(str(user["_id"]), {
                "oauth_provider": "microsoft",
                "oauth_id": ms_id,
            })
        else:
            user_id = await repo.create({
                "email": email,
                "name": userinfo.get("displayName", ""),
                "oauth_provider": "microsoft",
                "oauth_id": ms_id,
                "organization_id": "",
                "role": "account",
                "created_at": datetime.utcnow(),
            })
            user = await repo.get_by_id(user_id)

    token_pair = _create_token_pair(user)
    redirect_url = f"{settings.oauth_redirect_base_url}/login?token={token_pair.access_token}&refresh={token_pair.refresh_token}"
    return RedirectResponse(redirect_url)
