# Bouncer

A Redis-backed rate limiting service where an AI advisor dynamically adjusts throttle thresholds based on live traffic patterns. Built as a deployable FastAPI service with a standalone pip-installable middleware package.

## How it works

Every request is checked against a sliding window counter stored in Redis. The window is the last 60 seconds — not a fixed clock minute — so limits are enforced continuously. All counter operations run inside a Lua script for atomicity.

Every 30 seconds a background advisor reads the current block rate and adjusts per-tier limits up or down automatically. The advisor is mocked today; it is designed to be swapped for a Claude API call with no changes to the rest of the app.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/check` | Rate limit check for a client and tier |
| GET | `/stats` | Current traffic stats from Redis |
| GET | `/advisor` | View advisor recommendation without applying |
| POST | `/advisor/apply` | Apply advisor recommendation immediately |

## Running locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis
brew services start redis

# Start the app
python main.py
```

## Usage

```bash
# Check a request
curl -X POST localhost:8000/check \
  -H "Content-Type: application/json" \
  -d '{"client_id": "alice", "tier": "free"}'

# View traffic stats
curl localhost:8000/stats

# See what the advisor recommends
curl localhost:8000/advisor
```

## Tiers

| Tier | Default limit (requests/min) |
|------|------------------------------|
| free | 5 |
| pro | 30 |
| enterprise | 100 |

Limits are stored in Redis and updated live by the advisor — no restart needed.

## Load testing

```bash
locust --host=http://localhost:8000
```

Open `http://localhost:8089`, set users and spawn rate, and watch the advisor react to traffic in the logs.

## Middleware package

`bouncer-ratelimit` is a standalone pip-installable package. Add one line to protect every route in any FastAPI app:

```python
from bouncer_ratelimit import BouncerMiddleware

app = FastAPI()
app.add_middleware(BouncerMiddleware, redis_url="redis://localhost:6379")
```

Install it:

```bash
pip install -e ./bouncer-ratelimit
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `ANTHROPIC_API_KEY` | — | Required when swapping in real Claude |
| `ADVISOR_INTERVAL` | `30` | Seconds between advisor runs |

## Swapping in Claude

Replace `MockAdvisor.analyze()` in `app/advisor.py` with a Claude API call. Pass `stats` as context and parse the recommended adjustments from the response. No other files need to change.
