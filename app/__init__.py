import asyncio
import logging
import os
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.advisor import ClaudeAdvisor, make_advisor
from app.limiter import SlidingWindowLimiter
from app.routes import router

logger = logging.getLogger(__name__)

ADVISOR_INTERVAL = int(os.getenv("ADVISOR_INTERVAL", "30"))  # seconds


async def _advisor_loop(limiter: SlidingWindowLimiter, advisor: ClaudeAdvisor) -> None:
    while True:
        await asyncio.sleep(ADVISOR_INTERVAL)
        try:
            stats = await limiter.get_stats()
            result = await advisor.analyze(stats)
            if result["recommendation"] == "adjust":
                for tier, new_limit in result["adjustments"].items():
                    await limiter.set_limit(tier, new_limit)
                logger.info("Advisor adjusted limits: %s — %s", result["adjustments"], result["reason"])
            else:
                logger.info("Advisor held: %s", result["reason"])
        except Exception:
            logger.exception("Advisor loop error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    limiter = SlidingWindowLimiter(r)
    advisor = make_advisor()

    task = asyncio.create_task(_advisor_loop(limiter, advisor))
    logger.info("Advisor loop started (interval: %ss)", ADVISOR_INTERVAL)

    yield

    task.cancel()
    await r.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Bouncer", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app
