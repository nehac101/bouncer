import os
from typing import Literal

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.advisor import MockAdvisor
from app.limiter import SlidingWindowLimiter

router = APIRouter()
advisor = MockAdvisor()


async def get_limiter() -> SlidingWindowLimiter:
    r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    return SlidingWindowLimiter(r)


def _client_id(request: Request) -> str:
    return request.headers.get("X-Client-ID") or request.client.host


class CheckRequest(BaseModel):
    client_id: str
    tier: Literal["free", "pro", "enterprise"] = "free"


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/check")
async def check(
    body: CheckRequest,
    limiter: SlidingWindowLimiter = Depends(get_limiter),
):
    allowed, count, limit = await limiter.is_allowed(body.client_id, body.tier)
    payload = {
        "client_id": body.client_id,
        "tier": body.tier,
        "count": count,
        "limit": limit,
        "window_seconds": 60,
    }
    if not allowed:
        return JSONResponse(status_code=429, content={"allowed": False, **payload})
    return {"allowed": True, **payload}


@router.get("/request")
async def protected_request(
    request: Request,
    limiter: SlidingWindowLimiter = Depends(get_limiter),
):
    client_id = _client_id(request)
    allowed, count, limit = await limiter.is_allowed(client_id, "free")
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limited", "client_id": client_id, "count": count, "limit": limit},
        )
    return {"message": "ok", "client_id": client_id, "count": count, "limit": limit}


@router.get("/stats")
async def get_stats(limiter: SlidingWindowLimiter = Depends(get_limiter)):
    return await limiter.get_stats()


@router.get("/advisor")
async def advisor_recommend(limiter: SlidingWindowLimiter = Depends(get_limiter)):
    stats = await limiter.get_stats()
    result = advisor.analyze(stats)
    return {**result, "stats_snapshot": stats}


@router.post("/advisor/apply")
async def advisor_apply(limiter: SlidingWindowLimiter = Depends(get_limiter)):
    stats = await limiter.get_stats()
    result = advisor.analyze(stats)
    for tier, new_limit in result["adjustments"].items():
        await limiter.set_limit(tier, new_limit)
    return {**result, "applied": list(result["adjustments"].keys()), "stats_snapshot": stats}
