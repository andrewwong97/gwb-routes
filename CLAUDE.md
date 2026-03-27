# CLAUDE.md

## Project overview

GWB Routes is a FastAPI app that shows real-time George Washington Bridge commute times (4 routes: upper/lower level, each direction). It includes a dashboard UI, route recommendations, historical tracking, and request analytics.

Deployed as a Vercel serverless function. All HTTP routes map to `app/index.py`.

## Architecture

```
app/
  index.py          # FastAPI app, middleware, all route handlers
  api_client.py     # Google Maps Directions/Places API wrapper
  analytics.py      # Request logging + query methods (PostgreSQL)
  database.py       # PostgreSQL connection (NeonDB) + schema init
  history.py        # Historical route duration storage + aggregation
  routes_cache.py   # Redis cache for API responses (180s TTL)
  constants.py      # GWB route GPS coordinates
  response_models.py # Pydantic response schemas
static/
  index.html        # Dashboard frontend (vanilla JS, dark theme)
tests/              # pytest suite (mocked external deps)
```

**External services:** Google Maps API (required), NeonDB PostgreSQL (optional), Redis (optional), Sentry (optional). All optional services degrade gracefully.

## External services detail

- **Google Maps API** — Directions API for real-time traffic durations, Places API for address autocomplete. Required for core functionality.
- **Redis (Upstash)** — In-memory cache with 180s TTL. Used for caching route durations (`route:*` keys) and route recommendation results (`recommend:*` keys, JSON-serialized). Prefer Redis for any new short-lived caching needs since it's already wired up in `routes_cache.py`.
- **NeonDB PostgreSQL** — Persistent storage. Stores request analytics (`request_logs`), historical duration records (`duration_records`), route/location metadata (`routes`, `locations`). Use Postgres for data that needs to survive restarts or be queried historically. Hobby tier with 0.5 GB limit — be mindful of table growth.
- **Sentry** — Error tracking and custom metrics (cache hit/miss counters). Optional.

**Architectural guidance:** For caching (short TTL, repeated lookups), use Redis via `RoutesCache`. For persistent data (history, analytics, anything that needs SQL queries), use Postgres via `Database`/`HistoryStore`. Both degrade gracefully — always wrap in try/except and fall through to API calls if unavailable.

## Running tests

```bash
pip install -r requirements.txt
pip install pytest httpx
PYTHONPATH=app python -m pytest tests/ -v --tb=short
```

Tests mock all external APIs (Google Maps, database, Redis). No real credentials needed — set `GOOGLE_MAPS_API_KEY=test-key`.

CI runs on push/PR to main via `.github/workflows/python-ci.yml`.

## Key considerations

- **NeonDB is on hobby tier (0.5 GB limit).** The analytics middleware filters bot traffic by user-agent to avoid bloating `request_logs`. If storage grows, consider adding TTL-based cleanup (e.g., `DELETE FROM request_logs WHERE timestamp < NOW() - INTERVAL '30 days'`).
- **Google Maps API quota** is managed via Redis caching (3-min TTL) and Vercel edge cache headers.
- **IP privacy:** IPs are SHA256-hashed before storage — never stored raw.
- **Analytics endpoints** (`/analytics/*`) are excluded from logging to prevent feedback loops.
- Environment variables: `GOOGLE_MAPS_API_KEY` (required), `DATABASE_URL`, `REDIS_URL`, `SENTRY_DSN` (all optional).
