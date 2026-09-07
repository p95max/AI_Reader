"""Redis-backed cache for deterministic narration requests."""

from typing import Protocol

import redis.asyncio as redis

from app.core.config import Settings, get_settings


class NarrationCache(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, narration: str) -> None: ...


class RedisNarrationCache:
    """Stores generated narration in Redis with a bounded TTL."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self._ttl_seconds = settings.narration_cache_ttl_seconds
        self._client = redis.from_url(settings.redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, narration: str) -> None:
        await self._client.set(key, narration, ex=self._ttl_seconds)

    async def close(self) -> None:
        await self._client.aclose()
