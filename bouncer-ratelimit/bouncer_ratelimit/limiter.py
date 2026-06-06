import time
import uuid

import redis.asyncio as aioredis

WINDOW_MS = 60_000  # 1-minute sliding window

DEFAULT_TIER_LIMITS: dict[str, int] = {
    "free": 5,
    "pro": 30,
    "enterprise": 100,
}

# Atomically: fetch live limit, evict expired entries, check count, conditionally insert.
# KEYS[1] = sliding window key, KEYS[2] = config:limit:{tier}
# Returns [allowed (0|1), current_count, limit]
_LUA = """
local key         = KEYS[1]
local config_key  = KEYS[2]
local now         = tonumber(ARGV[1])
local window_ms   = tonumber(ARGV[2])
local default_lim = tonumber(ARGV[3])
local req_id      = ARGV[4]

local stored = redis.call('GET', config_key)
local limit  = stored and tonumber(stored) or default_lim

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window_ms)
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, req_id)
    redis.call('PEXPIRE', key, window_ms)
    return {1, count + 1, limit}
else
    return {0, count, limit}
end
"""


class SlidingWindowLimiter:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._script = self.redis.register_script(_LUA)

    async def _get_limit(self, tier: str) -> int:
        val = await self.redis.get(f"config:limit:{tier}")
        return int(val) if val else DEFAULT_TIER_LIMITS.get(tier, DEFAULT_TIER_LIMITS["free"])

    async def set_limit(self, tier: str, limit: int) -> None:
        await self.redis.set(f"config:limit:{tier}", limit)

    async def is_allowed(self, client_id: str, tier: str) -> tuple[bool, int, int]:
        now_ms = int(time.time() * 1000)
        req_id = f"{now_ms}-{uuid.uuid4().hex[:8]}"
        key = f"sliding:{tier}:{client_id}"
        config_key = f"config:limit:{tier}"
        default_limit = DEFAULT_TIER_LIMITS.get(tier, DEFAULT_TIER_LIMITS["free"])

        result = await self._script(
            keys=[key, config_key],
            args=[now_ms, WINDOW_MS, default_limit, req_id],
        )
        allowed, count, effective_limit = bool(result[0]), int(result[1]), int(result[2])

        await self.redis.incr("stats:allowed" if allowed else "stats:blocked")
        return allowed, count, effective_limit

    async def get_stats(self) -> dict:
        allowed = int(await self.redis.get("stats:allowed") or 0)
        blocked = int(await self.redis.get("stats:blocked") or 0)
        total = allowed + blocked

        tier_limits = {}
        for tier in DEFAULT_TIER_LIMITS:
            tier_limits[tier] = await self._get_limit(tier)

        return {
            "allowed": allowed,
            "blocked": blocked,
            "total": total,
            "block_rate": round(blocked / total, 3) if total > 0 else 0.0,
            "window_seconds": WINDOW_MS // 1000,
            "tier_limits": tier_limits,
        }

    async def reset_stats(self) -> None:
        await self.redis.delete("stats:allowed", "stats:blocked")
