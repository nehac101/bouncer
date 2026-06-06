import os

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.advisor import MockAdvisor
from app.limiter import RateLimiter

router = APIRouter()
advisor = MockAdvisor()


async def get_limiter() -> RateLimiter:
    r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    return RateLimiter(r)


def _client_id(request: Request) -> str:
    # Allow load tests to supply a synthetic client ID via header
    return request.headers.get("X-Client-ID") or request.client.host


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/request")
async def protected_request(
    request: Request,
    limiter: RateLimiter = Depends(get_limiter),
):
    client_id = _client_id(request)
    allowed, count, threshold = await limiter.is_allowed(client_id)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limited", "client_id": client_id, "count": count, "threshold": threshold},
        )
    return {"message": "ok", "client_id": client_id, "count": count, "threshold": threshold}


@router.get("/stats")
async def get_stats(limiter: RateLimiter = Depends(get_limiter)):
    return await limiter.get_stats()


@router.post("/admin/adjust")
async def adjust_threshold(limiter: RateLimiter = Depends(get_limiter)):
    stats = await limiter.get_stats()
    result = advisor.analyze(stats)
    if result["recommendation"] == "adjust":
        await limiter.set_threshold(result["new_threshold"])
    return {**result, "stats_snapshot": stats}
