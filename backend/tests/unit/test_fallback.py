"""Tests for the deterministic fallback chain."""
import pytest

from backend.core.stability.fallback import FallbackChain, FallbackLevel


@pytest.mark.asyncio
async def test_primary_succeeds():
    chain = FallbackChain(service_name="test")
    result, level = await chain.execute(
        primary_fn=lambda: _async_return("primary_result"),
    )
    assert result == "primary_result"
    assert level == FallbackLevel.PRIMARY


@pytest.mark.asyncio
async def test_primary_fails_secondary_succeeds():
    chain = FallbackChain(service_name="test")
    result, level = await chain.execute(
        primary_fn=lambda: _async_raise(RuntimeError("fail")),
        secondary_fn=lambda: _async_return("secondary_result"),
    )
    assert result == "secondary_result"
    assert level == FallbackLevel.SECONDARY


@pytest.mark.asyncio
async def test_all_fail_returns_fallback():
    chain = FallbackChain(service_name="test")
    result, level = await chain.execute(
        primary_fn=lambda: _async_raise(RuntimeError("fail")),
        secondary_fn=lambda: _async_raise(RuntimeError("fail")),
        fallback_fn=lambda: _async_return("fallback_result"),
    )
    assert result == "fallback_result"
    assert level == FallbackLevel.INTERNAL_ONLY


@pytest.mark.asyncio
async def test_all_fail_no_fallback_returns_none():
    chain = FallbackChain(service_name="test")
    result, level = await chain.execute(
        primary_fn=lambda: _async_raise(RuntimeError("fail")),
    )
    assert result is None
    assert level == FallbackLevel.TEMPLATE


async def _async_return(value):
    return value


async def _async_raise(exc):
    raise exc
