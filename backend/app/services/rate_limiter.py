"""Atomic rate limits with Redis acceleration and a transactional DB fallback."""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta

from redis.exceptions import RedisError
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.core.config import get_settings
from backend.app.core.redis import redis_client
from backend.app.db.models import RateLimitBucket
from backend.app.services.utc_time import as_utc, utc_now

settings = get_settings()
logger = logging.getLogger(__name__)


def _require_redis_in_production() -> bool:
    return settings.environment.lower() == "production"


_INCREMENT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


def _bucket_key(scope: str, identifier: str) -> str:
    key = settings.otp_hmac_key
    if not key:
        raise RuntimeError("OTP_HMAC_KEY is required for rate-limit keying")
    digest = hmac.new(key.encode(), identifier.encode(), hashlib.sha256).hexdigest()
    return f"otp:{scope}:{digest}"


async def consume_rate_limit(
    db: AsyncSession,
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    now: datetime | None = None,
) -> int | None:
    """Consume one request; return retry seconds when the limit is exceeded."""
    now = as_utc(now) if now is not None else utc_now()
    key = _bucket_key(scope, identifier)

    if redis_client is not None:
        try:
            lockout_ttl = int(await redis_client.ttl(f"{key}:lockout"))
            if lockout_ttl > 0:
                return lockout_ttl
            count = int(await redis_client.eval(_INCREMENT_SCRIPT, 1, key, window_seconds))
            ttl = max(1, int(await redis_client.ttl(key)))
            return ttl if count > limit else None
        except RedisError:
            logger.warning("Redis rate-limit operation failed; using database fallback")
            if _require_redis_in_production():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication rate limiting is unavailable",
                )
    elif _require_redis_in_production():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication rate limiting is unavailable",
        )

    bucket = await db.scalar(
        select(RateLimitBucket)
        .where(RateLimitBucket.bucket_key == key)
        .with_for_update()
    )
    if bucket is None:
        bucket = RateLimitBucket(
            bucket_key=key,
            window_started_at=now,
            request_count=0,
        )
        db.add(bucket)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            bucket = await db.scalar(
                select(RateLimitBucket)
                .where(RateLimitBucket.bucket_key == key)
                .with_for_update()
            )
            if bucket is None:
                raise

    if bucket.locked_until and as_utc(bucket.locked_until) > now:
        return max(1, int((as_utc(bucket.locked_until) - now).total_seconds()))
    window_started_at = as_utc(bucket.window_started_at)
    if now - window_started_at >= timedelta(seconds=window_seconds):
        window_started_at = now
        bucket.window_started_at = now
        bucket.request_count = 0
    bucket.request_count += 1
    if bucket.request_count > limit:
        return max(
            1,
            int(
                (
                    window_started_at
                    + timedelta(seconds=window_seconds)
                    - now
                ).total_seconds()
            ),
        )
    return None


async def set_lockout(
    db: AsyncSession,
    scope: str,
    identifier: str,
    duration_seconds: int,
    now: datetime | None = None,
) -> None:
    now = as_utc(now) if now is not None else utc_now()
    key = _bucket_key(scope, identifier)
    until = now + timedelta(seconds=duration_seconds)
    if redis_client is not None:
        try:
            await redis_client.set(f"{key}:lockout", "locked", ex=duration_seconds)
            return
        except RedisError:
            logger.warning("Redis lockout operation failed; using database fallback")
            if _require_redis_in_production():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication rate limiting is unavailable",
                )
    elif _require_redis_in_production():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication rate limiting is unavailable",
        )

    bucket = await db.scalar(
        select(RateLimitBucket)
        .where(RateLimitBucket.bucket_key == key)
        .with_for_update()
    )
    if bucket is None:
        bucket = RateLimitBucket(
            bucket_key=key,
            window_started_at=now,
            request_count=0,
            locked_until=until,
        )
        db.add(bucket)
    else:
        bucket.locked_until = until


async def cleanup_expired_rate_limit_buckets(
    db: AsyncSession,
    now: datetime | None = None,
) -> int:
    """Delete old unlocked database fallback buckets; safe to repeat after restarts."""
    now = as_utc(now) if now is not None else utc_now()
    cutoff = now - timedelta(hours=settings.rate_limit_bucket_retention_hours)
    result = await db.execute(
        delete(RateLimitBucket).where(
            RateLimitBucket.window_started_at < cutoff,
            (
                RateLimitBucket.locked_until.is_(None)
                | (RateLimitBucket.locked_until <= now)
            ),
        )
    )
    return int(result.rowcount or 0)
