import redis.asyncio as redis
from core.config import settings

class RedisClient:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self._redis = None

    async def get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def close(self):
        if self._redis:
            await self._redis.close()

# Singleton instance
redis_client = RedisClient()
