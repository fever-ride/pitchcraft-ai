"""Tests for auth JWT token creation and verification."""
from datetime import timedelta

import pytest
from jose import jwt

from backend.core.config import settings


def _create_test_token(data: dict, expires_delta: timedelta) -> str:
    from datetime import datetime
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + expires_delta
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def test_token_encode_decode():
    token = _create_test_token(
        {"sub": "user123", "org_id": "org456", "role": "account"},
        timedelta(minutes=60),
    )
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "user123"
    assert payload["org_id"] == "org456"
    assert payload["role"] == "account"


def test_expired_token_raises():
    token = _create_test_token(
        {"sub": "user123", "org_id": "org456", "role": "account"},
        timedelta(minutes=-1),
    )
    with pytest.raises(Exception):
        jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def test_invalid_secret_raises():
    token = _create_test_token(
        {"sub": "user123", "org_id": "org456", "role": "account"},
        timedelta(minutes=60),
    )
    with pytest.raises(Exception):
        jwt.decode(token, "wrong-secret", algorithms=[settings.jwt_algorithm])


def test_role_hierarchy():
    try:
        from backend.api.v1.permissions import Role, ROLE_HIERARCHY
        assert ROLE_HIERARCHY[Role.ACCOUNT] < ROLE_HIERARCHY[Role.LEAD_ACCOUNT]
        assert ROLE_HIERARCHY[Role.LEAD_ACCOUNT] < ROLE_HIERARCHY[Role.ADMIN]
    except ImportError:
        pytest.skip("FastAPI not installed in test environment")
