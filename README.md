# Mac App Opportunity Radar

Scans the Mac App Store for under-served niches with proven demand and weak incumbents, and scores each on whether it's worth building.

See [`PRD-mac-app-radar-v0.1.md`](./PRD-mac-app-radar-v0.1.md) (product) and [`TECH-PRD-mac-app-radar-v0.1.md`](./TECH-PRD-mac-app-radar-v0.1.md) (engineering). Build plan + milestones in [`TASKS.md`](./TASKS.md).

**Status:** M0 — scaffold. Scraping, scoring, and frontend not yet implemented.

## Architecture (target)

```
[GitHub Actions cron] ──daily──> Python scraper ──> Supabase (Postgres)
                                                          │
[Vite/React SPA] <──REST/RPC── Supabase <──reads─────────┘
       └── live JSONP probe ──> iTunes Search/Lookup
       └── serverless fn ──> Claude API (review clustering, buildability)
```

## Local setup

Requires Python 3.11+ (CI runs 3.12).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in secrets for pipeline runs (not needed for the M0 stub)
```

## Run

```bash
radar                                  # full daily scrape (M0: stub)
radar --keyword "android file transfer mac"   # score a single keyword (M0: stub)
python -m radar --version
```

## Develop

```bash
ruff check .
black --check .
pytest -q
```

## Config

| Var | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | pipeline | Postgres/REST endpoint |
| `SUPABASE_SERVICE_KEY` | pipeline | write access (Actions secret only) |
| `ANTHROPIC_API_KEY` | LLM jobs | Claude review clustering + buildability tagging |
| `RADAR_RATE_LIMIT_PER_MIN` | no (default 18) | iTunes token-bucket ceiling |
| `RADAR_STOREFRONT` | no (default `us`) | App Store country |

Secrets live in `.env` locally (gitignored) and GitHub Actions secrets in CI. Never ship keys in the SPA.

## Scoring

Weights + gate thresholds live in [`radar/weights.json`](./radar/weights.json) — the single source of truth shared by the Python scorer and (later) the TS live probe. Weights are config; tune them in M3.8 calibration, don't hardcode in functions.
