"""Redis connection shared by rate limiting and lifecycle workers."""

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.app.api.v1.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)
redis_client: Redis | None = (
    Redis.from_url(settings.redis_url, decode_responses=True)
    if settings.redis_url
    else None
)


async def check_redis() -> bool:
    if redis_client is None:
        return False
    try:
        return bool(await redis_client.ping())
    except RedisError:
        logger.warning("Redis unavailable; using database rate-limit fallback")
        return False


async def close_redis() -> None:
    if redis_client is not None:
        await redis_client.aclose()
