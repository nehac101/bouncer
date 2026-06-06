from app.limiter import MIN_THRESHOLD, MAX_THRESHOLD

# Mocked advisor — mimics what Claude would do:
# read traffic stats, reason about patterns, recommend a threshold change.


class MockAdvisor:
    def analyze(self, stats: dict) -> dict:
        threshold = stats["threshold"]
        block_rate = stats["block_rate"]
        total = stats["total"]

        if total < 10:
            return {
                "recommendation": "hold",
                "new_threshold": threshold,
                "reason": "Insufficient traffic data to make a decision.",
            }

        if block_rate > 0.30:
            new_threshold = min(int(threshold * 1.5), MAX_THRESHOLD)
            reason = (
                f"Block rate is {block_rate:.0%} — too many legitimate requests are "
                f"being rejected. Raising threshold from {threshold} to {new_threshold}."
            )
        elif block_rate < 0.05:
            new_threshold = max(int(threshold * 0.85), MIN_THRESHOLD)
            reason = (
                f"Block rate is only {block_rate:.0%} — system has headroom. "
                f"Tightening threshold from {threshold} to {new_threshold}."
            )
        else:
            new_threshold = threshold
            reason = (
                f"Block rate is {block_rate:.0%} — within acceptable range. "
                "No adjustment needed."
            )

        return {
            "recommendation": "adjust" if new_threshold != threshold else "hold",
            "new_threshold": new_threshold,
            "reason": reason,
        }
