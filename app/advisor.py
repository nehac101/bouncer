import json
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

_MIN: dict[str, int] = {"free": 2, "pro": 10, "enterprise": 50}
_MAX: dict[str, int] = {"free": 20, "pro": 100, "enterprise": 500}

_SYSTEM = """\
You are a rate limiter advisor. Given traffic stats, recommend whether to adjust per-tier request limits.

Respond with ONLY a valid JSON object — no markdown, no explanation, just the JSON:
{
  "recommendation": "adjust" or "hold",
  "adjustments": {"free": <int>, "pro": <int>, "enterprise": <int>},
  "reason": "<one sentence>"
}

Rules:
- Include in adjustments only tiers whose limit should change.
- block_rate > 0.30 → raise limits (too many requests rejected).
- block_rate < 0.05 → lower limits (headroom available).
- total < 10        → hold (insufficient data).
- Otherwise         → hold (healthy).
- Bounds: free 2–20, pro 10–100, enterprise 50–500 req/min.
"""


class MockAdvisor:
    async def analyze(self, stats: dict) -> dict:
        block_rate = stats["block_rate"]
        total = stats["total"]
        tier_limits = stats["tier_limits"]

        if total < 10:
            return {
                "recommendation": "hold",
                "adjustments": {},
                "reason": "Insufficient traffic data to make a decision.",
            }

        adjustments: dict[str, int] = {}
        for tier, current in tier_limits.items():
            if block_rate > 0.30:
                new = min(int(current * 1.5), _MAX[tier])
                if new != current:
                    adjustments[tier] = new
            elif block_rate < 0.05:
                new = max(int(current * 0.85), _MIN[tier])
                if new != current:
                    adjustments[tier] = new

        if block_rate > 0.30:
            reason = f"Block rate is {block_rate:.0%} — too many requests rejected. Raising limits."
        elif block_rate < 0.05:
            reason = f"Block rate is only {block_rate:.0%} — headroom available. Tightening limits."
        else:
            reason = f"Block rate is {block_rate:.0%} — within acceptable range. No adjustment needed."

        return {
            "recommendation": "adjust" if adjustments else "hold",
            "adjustments": adjustments,
            "reason": reason,
        }


class ClaudeAdvisor:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic()

    async def analyze(self, stats: dict) -> dict:
        if stats["total"] < 10:
            return {
                "recommendation": "hold",
                "adjustments": {},
                "reason": "Insufficient traffic data.",
            }

        try:
            response = await self._client.messages.create(
                model="claude-opus-4-8",
                max_tokens=512,
                thinking={"type": "adaptive"},
                system=_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Current stats:\n"
                            f"- total_requests: {stats['total']}\n"
                            f"- block_rate: {stats['block_rate']:.2%}\n"
                            f"- tier_limits: {stats['tier_limits']}\n\n"
                            "What adjustments do you recommend?"
                        ),
                    }
                ],
            )
            text = next(b.text for b in response.content if b.type == "text")
            result = json.loads(text)

            clamped: dict[str, int] = {}
            for tier, new_limit in result.get("adjustments", {}).items():
                if tier in _MIN:
                    clamped[tier] = max(_MIN[tier], min(int(new_limit), _MAX[tier]))

            result["adjustments"] = clamped
            result["recommendation"] = "adjust" if clamped else "hold"
            return result

        except Exception:
            logger.exception("Claude advisor call failed")
            return {
                "recommendation": "hold",
                "adjustments": {},
                "reason": "Advisor unavailable — defaulting to hold.",
            }


def make_advisor() -> MockAdvisor | ClaudeAdvisor:
    if os.getenv("ADVISOR_BACKEND", "claude").lower() == "mock":
        logger.info("Using MockAdvisor")
        return MockAdvisor()
    logger.info("Using ClaudeAdvisor")
    return ClaudeAdvisor()
