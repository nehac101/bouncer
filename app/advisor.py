from app.limiter import DEFAULT_TIER_LIMITS

# Mocked advisor — mimics what Claude would do:
# read traffic stats, reason about patterns, recommend per-tier limit changes.

_MIN: dict[str, int] = {"free": 2, "pro": 10, "enterprise": 50}
_MAX: dict[str, int] = {"free": 20, "pro": 100, "enterprise": 500}


class MockAdvisor:
    def analyze(self, stats: dict) -> dict:
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
            reason = (
                f"Block rate is {block_rate:.0%} — too many requests rejected. "
                "Raising limits across tiers."
            )
        elif block_rate < 0.05:
            reason = (
                f"Block rate is only {block_rate:.0%} — headroom available. "
                "Tightening limits across tiers."
            )
        else:
            reason = (
                f"Block rate is {block_rate:.0%} — within acceptable range. "
                "No adjustment needed."
            )

        return {
            "recommendation": "adjust" if adjustments else "hold",
            "adjustments": adjustments,
            "reason": reason,
        }
