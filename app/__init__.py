import asyncio
import logging
import os
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from app.advisor import MockAdvisor
from app.limiter import SlidingWindowLimiter
from app.routes import router

logger = logging.getLogger(__name__)

ADVISOR_INTERVAL = int(os.getenv("ADVISOR_INTERVAL", "30"))  # seconds


async def _advisor_loop(limiter: SlidingWindowLimiter, advisor: MockAdvisor) -> None:
    while True:
        await asyncio.sleep(ADVISOR_INTERVAL)
        try:
            stats = await limiter.get_stats()
            result = advisor.analyze(stats)
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
    advisor = MockAdvisor()

    task = asyncio.create_task(_advisor_loop(limiter, advisor))
    logger.info("Advisor loop started (interval: %ss)", ADVISOR_INTERVAL)

    yield

    task.cancel()
    await r.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Bouncer", lifespan=lifespan)
    app.include_router(router)
    return app
