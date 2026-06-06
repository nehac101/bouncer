import time
import redis.asyncio as aioredis

WINDOW_SIZE = 60  # seconds
DEFAULT_THRESHOLD = 10  # requests per window
MIN_THRESHOLD = 3
MAX_THRESHOLD = 100


class RateLimiter:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def get_threshold(self) -> int:
        val = await self.redis.get("config:threshold")
        return int(val) if val else DEFAULT_THRESHOLD

    async def set_threshold(self, threshold: int) -> None:
        await self.redis.set("config:threshold", threshold)

    async def is_allowed(self, client_id: str) -> tuple[bool, int, int]:
        window = int(time.time()) // WINDOW_SIZE
        key = f"rate:{client_id}:{window}"
        threshold = await self.get_threshold()

        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, WINDOW_SIZE * 2)

        if count <= threshold:
            await self.redis.incr("stats:allowed")
        else:
            await self.redis.incr("stats:blocked")

        return count <= threshold, count, threshold

    async def get_stats(self) -> dict:
        allowed = int(await self.redis.get("stats:allowed") or 0)
        blocked = int(await self.redis.get("stats:blocked") or 0)
        threshold = await self.get_threshold()
        total = allowed + blocked
        return {
            "allowed": allowed,
            "blocked": blocked,
            "total": total,
            "block_rate": round(blocked / total, 3) if total > 0 else 0.0,
            "threshold": threshold,
        }

    async def reset_stats(self) -> None:
        await self.redis.delete("stats:allowed", "stats:blocked")
