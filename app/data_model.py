"""
Redis Data Model
================

All keys used by Bouncer, their types, and what they store.

──────────────────────────────────────────────────────────────────
SLIDING WINDOW COUNTERS
──────────────────────────────────────────────────────────────────

Key pattern : sliding:{tier}:{client_id}
Type        : Sorted Set (ZSET)
TTL         : WINDOW_MS (60 seconds), reset on each new request
Example key : sliding:free:alice

Each member is a unique request ID: "{timestamp_ms}-{8 hex chars}"
The score   is the request timestamp in milliseconds.

This structure lets us efficiently evict entries outside the window
with ZREMRANGEBYSCORE and count remaining entries with ZCARD.

    Member                   Score (ms timestamp)
    ───────────────────────  ────────────────────
    "1748120000000-a3f2c1d0"  1748120000000
    "1748120001500-b7e4f2a1"  1748120001500
    "1748120003000-c9d3e0b2"  1748120003000

──────────────────────────────────────────────────────────────────
TIER LIMIT CONFIG
──────────────────────────────────────────────────────────────────

Key pattern : config:limit:{tier}
Type        : String (integer stored as string)
TTL         : None (persists until explicitly changed)
Example key : config:limit:free

Stores the live request limit for a tier. Written by the advisor
via POST /admin/adjust. If absent, the in-code DEFAULT_TIER_LIMITS
fallback is used.

    Key                    Value
    ─────────────────────  ─────
    config:limit:free       "5"
    config:limit:pro        "30"
    config:limit:enterprise "100"

──────────────────────────────────────────────────────────────────
GLOBAL STATS COUNTERS
──────────────────────────────────────────────────────────────────

Key         : stats:allowed
Key         : stats:blocked
Type        : String (integer, incremented with INCR)
TTL         : None (lifetime counters, reset via /admin/reset)

Running totals across all clients and tiers. Used by the advisor
to compute block_rate and decide whether to adjust tier limits.

    Key            Value
    ─────────────  ──────
    stats:allowed  "1042"
    stats:blocked  "87"
"""
