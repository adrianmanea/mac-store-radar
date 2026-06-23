# Technical PRD — Mac App Opportunity Radar (working name)

**Version:** v0.1
**Owner:** Adrian
**Status:** Draft for review
**Companion doc:** Product PRD v0.1
**Scope of this doc:** system architecture, data model, scraper pipeline, rate-limit strategy, scoring engine, LLM integration, infra, cost. Engineering-facing.

---

## 0. The rate-limit question, settled first

> **"Do we run daily to avoid rate limits?"** No — daily cadence is for the *momentum signal*. Rate limits are solved *inside* each run.

Two separate concerns that are easy to conflate:

- **How often we run** is set by momentum sampling. Rating counts drift slowly; one snapshot/day is the right granularity. More frequent = noise, not signal. Less frequent = coarse velocity.
- **Rate limits** are a per-run throughput problem. A single daily run that looks up thousands of apps will exceed the ceiling unless throttled. The cadence doesn't fix that; the request design does.

**The iTunes API ceiling** is not officially published by Apple. Empirically it's ~20 requests/minute per IP, with HTTP 403 on breach. Design defensively against that number, don't trust it as a contract.

**The three mitigations that actually matter:**

1. **Batch the Lookup API.** `lookup?id=111,222,333,...` accepts a comma-separated list (~150–200 IDs/call is safe before URL length bites). This is the single biggest lever: a niche scan touching 3,000 unique apps becomes ~15–20 lookup calls, not 3,000.
2. **Throttle within the run.** Token-bucket pace all calls to stay under ~18/min (headroom below 20). Exponential backoff + retry on 403.
3. **Cache + persist.** Store every raw response. Re-scoring never re-fetches. Each app's metadata is fetched at most once per day (the snapshot).

**Where the real cost is — reviews, not metadata.** Review RSS is paginated (~10 pages × ~50 reviews). Fetching reviews for 500 apps × 10 pages = 5,000 calls ≈ 4+ hours at the ceiling. So we **do not** fetch reviews for everything daily. Reviews are fetched on a **rotating, bounded cadence**: new apps immediately, watched-niche apps weekly, everything else on a slow rotation. This keeps the daily run well under an hour. (See §4.4.)

---

## 1. System architecture

```
                        ┌─────────────────────────────┐
   daily schedule  ───> │  GitHub Actions (Python)    │
                        │  scraper + scorer pipeline  │
                        └──────────────┬──────────────┘
                                       │ writes
                          ┌────────────▼────────────┐
   iTunes Search/Lookup   │   Supabase (Postgres)   │
   /reviews RSS  ◀────────┤   apps, snapshots,      │
                          │   niches, reviews,      │
                          │   scores, runs          │
                          └────────────┬────────────┘
                                       │ REST/RPC (anon key + RLS)
                          ┌────────────▼────────────┐
                          │   Vite/React SPA        │
                          │   (Cloudflare Pages)    │
                          └────────────┬────────────┘
                                       │ on-demand
                          ┌────────────▼────────────┐
   live ad-hoc scoring    │  iTunes API via JSONP   │  (Phase 0 + live keyword probe)
                          └─────────────────────────┘

   LLM jobs (async, separate Action or queue):
     reviews ──> Claude (Sonnet) ──> unmet-need clusters
     new apps ──> Claude (Haiku) ──> buildability class
```

**Component responsibilities**

- **Scraper/scorer (Python, GitHub Actions):** scheduled batch. Resolves niches → search → dedupe → batched lookup → upsert apps + insert snapshots → bounded review fetch → compute scores → write. Stateless between runs; all state in Postgres.
- **Supabase Postgres:** system of record + auto REST/RPC API the SPA reads. RLS on. Service-role key only in Actions secrets.
- **Vite/React SPA:** read-only dashboard over Supabase, plus a live ad-hoc keyword probe that calls the iTunes API directly via JSONP (no backend hop) for instant scoring of a keyword not yet in the DB.
- **LLM jobs:** decoupled from the scrape so a slow/expensive Claude call never blocks data collection. Triggered after the scrape writes new rows.

**Why this split:** stateless scoring can live client-side (iTunes JSONP `callback` sidesteps CORS), so Phase 0 needs no backend at all. Momentum forces persistence → the only reason a backend exists. GitHub Actions gives free scheduled compute and keeps scraping in Python; Supabase removes all DB ops and is productizable later. (Full rationale in product PRD §7.)

---

## 2. Data model

```sql
-- Canonical app record (one row per Apple track id)
create table apps (
  app_id              bigint primary key,        -- iTunes trackId
  bundle_id           text,
  name                text not null,
  developer_id        bigint,
  developer_name      text,
  category            text,
  price               numeric,
  currency            text,
  has_iap             boolean,
  is_subscription     boolean,                   -- inferred from IAP names/metadata
  release_date        timestamptz,
  current_ver_date    timestamptz,               -- freshness / maintenance signal
  description         text,
  complexity_class    text,                      -- LLM-tagged: 'wrapper'|'integration'|'native_complex'
  complexity_at       timestamptz,
  first_seen          timestamptz default now(),
  last_seen           timestamptz default now()
);

-- Time-series: the spine of momentum. One row per app per run.
create table app_snapshots (
  id             bigserial primary key,
  app_id         bigint references apps(app_id),
  captured_at    timestamptz not null,
  rating_count   integer,
  avg_rating     numeric,
  price          numeric,
  version        text,
  chart_rank     integer,                        -- nullable; from chart feeds when available
  unique (app_id, captured_at)
);
create index on app_snapshots (app_id, captured_at desc);

-- Niches = the search keywords we track
create table niches (
  id           bigserial primary key,
  keyword      text not null unique,
  display_name text,
  storefront   text default 'us',
  is_watched   boolean default true,             -- watched = reviews refreshed weekly
  created_at   timestamptz default now()
);

-- Which apps appeared for a niche, with rank, over time
create table niche_apps (
  niche_id      bigint references niches(id),
  app_id        bigint references apps(app_id),
  search_rank   integer,
  captured_at   timestamptz not null,
  primary key (niche_id, app_id, captured_at)
);

-- Computed score snapshots per niche (so scores are themselves a time-series)
create table niche_scores (
  id            bigserial primary key,
  niche_id      bigint references niches(id),
  captured_at   timestamptz not null,
  demand        numeric,
  competition   numeric,
  gap           numeric,
  monetization  numeric,
  buildability  numeric,
  opportunity   numeric,
  momentum      numeric,
  gated_out     boolean default false,           -- failed a hard gate
  gate_reason   text,
  raw_inputs    jsonb,                            -- every input, for traceability
  unique (niche_id, captured_at)
);

-- Reviews for gap mining
create table reviews (
  id            bigserial primary key,
  app_id        bigint references apps(app_id),
  apple_review_id text,
  rating        integer,
  title         text,
  body          text,
  author        text,
  submitted_at  timestamptz,
  fetched_at    timestamptz default now(),
  unique (app_id, apple_review_id)
);

-- LLM-clustered unmet needs (per app, rolled up to niche in queries)
create table unmet_needs (
  id            bigserial primary key,
  app_id        bigint references apps(app_id),
  theme         text,
  frequency     integer,                          -- how many reviews hit this theme
  severity      text,                             -- 'low'|'med'|'high'
  example_ids   jsonb,                            -- apple_review_ids
  generated_at  timestamptz default now()
);

-- Demand proxy signals (separate cadence, slow-moving)
create table demand_signals (
  niche_id          bigint references niches(id),
  autocomplete_depth integer,
  google_volume      integer,
  captured_at        timestamptz not null,
  primary key (niche_id, captured_at)
);

-- Run metadata for observability
create table scrape_runs (
  id            bigserial primary key,
  started_at    timestamptz default now(),
  finished_at   timestamptz,
  status        text,                             -- 'ok'|'partial'|'failed'
  apps_seen     integer,
  apps_new      integer,
  api_calls     integer,
  http_403s     integer,
  notes         text
);
```

**Momentum query (window function over snapshots):**

```sql
-- per-app daily velocity, then averaged to niche level
with deltas as (
  select app_id, captured_at, rating_count,
         rating_count - lag(rating_count)
           over (partition by app_id order by captured_at) as d_ratings,
         extract(epoch from captured_at
           - lag(captured_at) over (partition by app_id order by captured_at))/86400 as d_days
  from app_snapshots
)
select app_id, d_ratings / nullif(d_days,0) as ratings_per_day
from deltas where d_days is not null;
```

---

## 3. External data contracts (adapters)

Each external source sits behind one adapter module so a breakage is a one-file fix.

| Adapter | Endpoint shape | Returns | Notes |
|---|---|---|---|
| `search` | `itunes.apple.com/search?term=&entity=macSoftware&country=us&limit=200` | up to 200 apps | 1 call per keyword |
| `lookup` | `itunes.apple.com/lookup?id=ID1,ID2,...` | metadata per id | **batch ~150–200 ids/call** |
| `reviews` | `itunes.apple.com/{cc}/rss/customerreviews/id={id}/sortBy=mostRecent/page={n}/json` | recent reviews | paginated, recent-only, ~500 cap |
| `charts` | RSS chart generator (verify current form for Mac) | top free/paid/grossing | **flaky for Mac — fallback: paid/sub ratio from metadata** |
| `autocomplete` | App Store search hints (unofficial) | suggestion list | isolate; may break without notice |

All adapters: shared token-bucket limiter (~18/min), retry-with-backoff on 403/timeout, raw response persisted before parse.

---

## 4. Scraper pipeline (daily run)

### 4.1 Niche resolution → search
For each `is_watched` niche: one Search call (`limit=200`). Record `niche_apps` rows with `search_rank` and today's timestamp. ~50 niches ≈ 50 calls ≈ <3 min at the ceiling.

### 4.2 Dedupe
Union all app IDs across all niches into a unique set. A single app appearing in 5 niches is fetched once.

### 4.3 Batched lookup → upsert + snapshot
Chunk unique IDs into groups of ~150. One Lookup call per chunk. For each app: `upsert apps` (update `last_seen`, metadata), `insert app_snapshots` (rating_count, avg_rating, price, version). 3,000 unique apps ≈ 20 calls ≈ ~1 min.

### 4.4 Bounded review fetch (the throttled part)
Select review targets by priority, capped per run (e.g. max 150 apps/run):
- **new apps** (first_seen today) → fetch now;
- **watched-niche apps not refreshed in 7 days** → fetch;
- **everything else** → slow rotation, oldest `fetched_at` first.

This bounds the heaviest cost so the run stays <1 hour regardless of catalog size. Insert into `reviews` (dedupe on `apple_review_id`).

### 4.5 Score computation
For each niche, pull latest snapshots for its apps + latest `demand_signals` + review-derived gap inputs → run scoring engine (§5) → write `niche_scores` row. Pure compute, no API.

### 4.6 Run record
Write `scrape_runs` summary (counts, 403s, status). Action fails loudly on `status='failed'`.

### 4.7 LLM jobs (decoupled)
Separate Action/step after the scrape:
- new/updated review batches → Claude (Sonnet) → `unmet_needs`;
- apps missing `complexity_class` → Claude (Haiku) → tag.
Batched to control cost (§6). Never blocks data collection.

---

## 5. Scoring engine

Pure function: `inputs (from DB) → sub-scores → gates → opportunity & momentum`. Lives in Python (server, source of truth) and is mirrored in TS for the live client probe — **one shared JSON spec of weights/thresholds** so the two never drift. Weights are config, not code.

```python
# pseudocode
def score_niche(niche, apps, snapshots, demand, reviews_gap, weights):
    D = demand_score(apps, demand)             # log(total ratings) + web vol + autocomplete depth
    C = competition_score(apps)                # count>floor + concentration (HHI) + incumbent quality
    G = gap_score(apps, reviews_gap)           # high_volume * low_avg_rating + complaint density
    M = monetization_score(apps)               # %paid/sub + price points + grossing presence
    B = buildability_multiplier(apps)          # from LLM complexity_class

    gate, reason = check_gates(D, M, B, weights)   # zero out if fails
    if gate:
        return Score(opportunity=0, gated_out=True, gate_reason=reason, ...)

    opportunity = (D * G * M) / max(C, 1) * B
    momentum    = niche_velocity(snapshots)        # normalized Δratings/Δt across niche
    return Score(D, C, G, M, B, opportunity, momentum, raw_inputs=...)
```

Each sub-score normalized 0–100. `raw_inputs` (jsonb) persists every term so any number in the UI is traceable to its source. **Gates run before the blend** (no monetization / unbuildable / sub-floor demand → hard zero).

---

## 6. LLM integration

- **Review clustering (gap):** batch ~40–60 reviews/app into one prompt → JSON out (`theme`, `frequency`, `severity`, `example_ids`). Model: Sonnet (judgment matters). Strict "JSON only, no prose" instruction; parse defensively, strip fences.
- **Buildability tagging:** one short prompt per new app from its description → `wrapper|integration|native_complex`. Model: Haiku (cheap, classification).
- **Cost control:** only run on *new/changed* data, never re-process. Batch. Cap apps/run. Rough envelope: tagging ~tens of apps/day on Haiku + clustering ~tens of apps/day on Sonnet → low single-digit to low-tens of USD/month at modest volume. Track token spend in `scrape_runs.notes`.
- **Key handling:** Anthropic key only in Actions secrets / serverless env. Never in the SPA. The client probe (Phase 0) skips LLM gap or routes through a thin serverless proxy.

---

## 7. Frontend

- **Stack:** Vite + React + TS, Tailwind. Hosted on Cloudflare Pages.
- **Data:** read-only via Supabase JS (anon key, RLS read policies). No writes from client.
- **Views:** (1) niche table sortable by Opportunity/Momentum; (2) Opportunity × Momentum scatter (the quadrant map); (3) niche drill-down — incumbent list, per-app rating history sparkline, version cadence, clustered unmet needs; (4) **live probe** — type a keyword, client calls iTunes via JSONP, computes sub-scores instantly using the shared TS scoring spec, no DB round-trip.
- **Design states:** real empty/loading(skeleton)/error states; momentum shown with explicit "estimate" labeling on the demand axis (no false precision).

---

## 8. Infrastructure & deployment

**Scheduler — GitHub Actions:**

```yaml
name: daily-scrape
on:
  schedule:
    - cron: '0 6 * * *'        # 06:00 UTC daily (Actions cron can lag under load; fine for daily)
  workflow_dispatch: {}         # manual trigger for testing
jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 90         # well under the 6h job cap
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: python -m radar.run
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

Notes: public repo = unlimited Actions minutes; private = 2,000 free min/month (a ~30–60 min daily run fits). Scheduled triggers are best-effort (can be delayed minutes under GitHub load) — acceptable for a daily snapshot. `workflow_dispatch` for on-demand reruns.

**DB — Supabase:** free tier covers Phase 1 (Postgres + auto API). RLS on; service role only in Actions. pg_cron available later if we want in-DB scheduling instead of Actions.

**Secrets:** `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, any chart/autocomplete keys → Actions secrets only.

## 9. Failure modes & observability

| Failure | Detection | Handling |
|---|---|---|
| 403 rate-limit | HTTP status | backoff+retry; if persistent, mark run `partial`, resume next day |
| Adapter schema change (autocomplete/charts) | parse error in one adapter | isolated; degrade that signal, continue run |
| Mac chart feed missing | empty/err | fallback to paid/sub ratio from metadata |
| LLM JSON parse fail | exception | retry once, else skip that app's clustering, log |
| Partial run | `scrape_runs.status` | dashboard banner; next run self-heals via rotation |
| Action failure | GitHub notification | manual `workflow_dispatch` after fix |

Every run writes a `scrape_runs` row (counts, 403s, token spend). That table is the health dashboard.

## 10. Security & ToS

- Public, documented APIs intended for affiliate/search use. Stay under rate limits; don't redistribute raw Apple data if productized.
- No PII stored beyond public review author handles. Reviews are public.
- Keys server-side only. SPA gets anon key + read-only RLS.
- **Revisit Apple ToS before any commercial launch** (redistribution + commercial-use clauses).

## 11. Build sequence

1. **Adapters + limiter** (search, lookup-batched, reviews) with the token bucket + raw persistence. Prove rate-limit behavior against real 403s.
2. **Schema + upsert/snapshot** writers. Run the scrape for a handful of niches, confirm snapshots accumulate.
3. **Scoring engine** (Python) + shared weights JSON. Backfill scores; calibrate against your 15–20 gut-check niches (product PRD exit criterion).
4. **Momentum** once ≥2 days of snapshots exist — validate velocity against a known riser retroactively.
5. **Frontend** read-only dashboard + live JSONP probe (mirror scoring spec in TS).
6. **LLM jobs** (clustering, tagging) decoupled.
7. **Observability** polish + watchlist/alerts.

## 12. Open technical questions

- Lookup batch size: confirm the safe ID-count ceiling empirically (URL length) — 150 vs 200.
- Review rotation cap per run: what daily app-count keeps the run under target wall-clock without starving the gap signal?
- Charts: is a usable Mac top-grossing feed actually available, or do we commit to the metadata-ratio fallback from day one?
- Single IP vs rotating egress: GitHub Actions runners share IP ranges — do we ever hit shared-IP rate limits, and is a small proxy pool worth it later?
- Scoring weights: hand-tuned config vs fitted against a labeled niche set — and where does the labeled set come from?
