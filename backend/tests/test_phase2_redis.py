import os
import uuid

import pytest
from redis.asyncio import Redis
from sqlalchemy.engine import make_url

from backend.app.services import rate_limiter


@pytest.mark.asyncio
async def test_disposable_redis_rate_limit_and_lockout(monkeypatch):
    url = os.getenv("TEST_REDIS_URL")
    if not url:
        pytest.skip(
            "Set TEST_REDIS_URL to the disposable loopback Redis instance on port 56379"
        )
    parsed = make_url(url)
    if (
        parsed.host not in {"localhost", "127.0.0.1", "::1"}
        or parsed.port != 56379
    ):
        raise RuntimeError(
            "Tests refuse Redis targets other than the disposable loopback instance on port 56379"
        )

    client = Redis.from_url(url, decode_responses=True)
    await client.ping()
    monkeypatch.setattr(rate_limiter, "redis_client", client)
    monkeypatch.setattr(rate_limiter.settings, "otp_hmac_key", "redis-test-hmac-key")
    identifier = f"redis-test-{uuid.uuid4().hex}"
    key = rate_limiter._bucket_key("request-phone", identifier)
    try:
        assert await rate_limiter.consume_rate_limit(
            None, "request-phone", identifier, limit=1, window_seconds=60
        ) is None
        exceeded = await rate_limiter.consume_rate_limit(
            None, "request-phone", identifier, limit=1, window_seconds=60
        )
        assert exceeded is not None and exceeded > 0

        await rate_limiter.set_lockout(
            None, "request-phone", identifier, duration_seconds=30
        )
        lockout = await rate_limiter.consume_rate_limit(
            None, "request-phone", identifier, limit=10, window_seconds=60
        )
        assert lockout is not None and 0 < lockout <= 30
    finally:
        await client.delete(key, f"{key}:lockout")
        await client.aclose()
