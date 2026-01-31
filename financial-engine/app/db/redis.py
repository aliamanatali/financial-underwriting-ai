import redis.asyncio as redis
from app.config import settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RedisManager:
    client: Optional[redis.Redis] = None

    async def connect(self):
        """Initialize Redis connection"""
        if not settings.redis_url:
            logger.warning("Redis URL not set. Skipping Redis connection.")
            return
        
        try:
            self.client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
            await self.client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")
            self.client = None

    async def get(self, key: str) -> Optional[str]:
        if not self.client:
            return None
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: str, expire: int = None):
        if not self.client:
            return
        try:
            if expire:
                await self.client.set(key, value, ex=expire)
            else:
                await self.client.set(key, value)
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    async def delete(self, key: str):
        if not self.client:
            return
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")

redis_client = RedisManager()

async def get_redis() -> Optional[redis.Redis]:
    return redis_client.client