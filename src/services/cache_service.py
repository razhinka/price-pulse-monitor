import json
import logging
from typing import Any

import redis.asyncio as aioredis

from src.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

    async def get_json(self, key: str) -> Any | None:
        try:
            await self.connect()
            assert self._redis is not None
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Redis read error for key %s: %s", key, exc)
            return None

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        try:
            await self.connect()
            assert self._redis is not None
            expire = ttl or settings.cache_ttl_seconds
            await self._redis.set(key, json.dumps(value), ex=expire)
        except Exception as exc:
            logger.warning("Redis write error for key %s: %s", key, exc)

    async def invalidate_all(self) -> None:
        """Сбрасывает кэш витрины и метрик после парсинга или добавления товара."""
        try:
            await self.connect()
            assert self._redis is not None
            await self._redis.delete("pulse:metrics", "pulse:items")
        except Exception as exc:
            logger.warning("Redis cache invalidation error: %s", exc)

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()


cache_service = CacheService()
