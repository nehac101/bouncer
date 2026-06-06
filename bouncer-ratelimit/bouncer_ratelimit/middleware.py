from typing import Callable

import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from bouncer_ratelimit.limiter import SlidingWindowLimiter


class BouncerMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter middleware for FastAPI/Starlette.

    Usage:
        app.add_middleware(BouncerMiddleware, redis_url="redis://localhost:6379")

    Reads client identity from X-Client-ID header (falls back to remote IP).
    Reads tier from X-Tier header (falls back to "free").
    """

    def __init__(
        self,
        app,
        redis_url: str = "redis://localhost:6379",
        excluded_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.excluded_paths = set(excluded_paths or ["/health", "/docs", "/openapi.json"])
        self.limiter = SlidingWindowLimiter(aioredis.from_url(redis_url))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        client_id = request.headers.get("X-Client-ID") or request.client.host
        tier = request.headers.get("X-Tier", "free")

        allowed, count, limit = await self.limiter.is_allowed(client_id, tier)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "client_id": client_id,
                    "tier": tier,
                    "count": count,
                    "limit": limit,
                },
            )
        return await call_next(request)
