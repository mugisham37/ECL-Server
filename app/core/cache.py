from redis.asyncio import Redis

from app.config import get_settings

_redis: Redis | None = None


async def get_redis_client() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def blacklist_token(redis: Redis, jti: str, ttl: int) -> None:
    if ttl > 0:
        await redis.setex(f"blacklist:jti:{jti}", ttl, "1")


async def is_token_blacklisted(redis: Redis, jti: str) -> bool:
    return await redis.exists(f"blacklist:jti:{jti}") > 0
