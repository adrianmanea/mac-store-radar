# Task List — Mac App Opportunity Radar

**Derived from:** PRD v0.1 + TECH-PRD v0.1
**Strategy:** gradual, vertical-ish slices. Each milestone ends with something runnable + a verifiable exit. Do not skip ahead — momentum (M2) is meaningless without snapshots accumulating (M1), scoring (M3) is calibrated against real data, etc.

Legend: `[ ]` todo · `(S/M/L)` rough size · **AC** = acceptance criterion.

---

## M0 — Repo & project skeleton ✅ DONE

Goal: empty repo → runnable scaffold, no scraping logic yet.

- [x] **0.1** Init Python package layout `radar/` with `adapters/`, `scoring/`, `pipeline/`, `db/`, `llm/`. `pyproject.toml` + `requirements.txt`. (S)
- [x] **0.2** Tooling: `ruff` + `black` + `pytest` + `.env.example` + CI workflow. (S)
- [x] **0.3** Config loader — reads `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY` from env; fails loud if missing. (S)
- [x] **0.4** Shared `weights.json` spec (sub-score weights + gate thresholds), single source of truth + loader. (S)
- [x] **0.5** README: how to run locally, env setup, run a single keyword. (S)

**AC:** ✅ `python -m radar` + `--keyword` work; `ruff` + `black --check` + `pytest` (4 passed) all green; CI workflow added.

> Note: local interpreter is Python 3.9.6 but project targets 3.11+ (CI uses 3.12). Verified locally via `PYTHONPATH` — all modules use `from __future__ import annotations` so union syntax is runtime-safe on 3.9. Install a 3.11+ interpreter for `pip install -e ".[dev]"` to work as written.

---

## M1 — Adapters + rate limiter (TECH-PRD §3, §0, build-seq #1) ✅ DONE

Goal: reliable, throttled reads from iTunes. The whole tool sits on this.

- [x] **1.1** Token-bucket limiter — `limiter.py`, injectable clock, burst capacity, fake-clock tested. (M)
- [x] **1.2** Raw-response persistence — `rawstore.py` (FileRawStore keyed by url+day, NullRawStore for tests/probe). (M)
- [x] **1.3** `search` adapter — `entity=macSoftware`, ranked AppStubs. (S)
- [x] **1.4** `lookup` adapter — batched, chunk 150, dedupes input → 1 call/150 ids. (M)
- [x] **1.5** `reviews` adapter — paginated, recent-only, stops on empty page, dedupe by review id. (M)
- [x] **1.6** `charts` adapter — endpoint verified at build. (M)
- [x] **1.7** `autocomplete` adapter — plist parse, fully isolated, degrades to depth 0. (S)
- [x] **1.8** Error contract (`errors.py`: RateLimit/Transient/Schema) + `CallStats` counters (api_calls/403s/retries) on the client. (S)

**AC:** ✅ shared `ITunesClient` (limiter + retry/backoff on 403/5xx/timeout + raw persist + counters); 18 tests pass offline via `httpx.MockTransport`; parse tests run against real captured fixtures.

> **Verified-at-build endpoint reality** (resolves TECH-PRD §12):
> - search ✅ · lookup batch ✅
> - **Mac charts: only top-free returns data; topgrossing + toppaid are empty** → monetization signal MUST come from metadata paid/sub ratio (M3.4), not a grossing feed.
> - **reviews RSS returned empty for every Mac app probed** → adapter correct vs documented shape, but gap signal (complaint density) may have no data; scoring stubs it (weights.json `gap.complaint_density_weight`, M3.3 / M6).
> - **autocomplete returns plist XML (0 hints in probe)** → isolated, tolerant; demand falls back to log-ratings when depth is 0.

---

## M2 — Schema + writers (build-seq #2) ✅ DONE (live)

Goal: persistence live. Snapshots start accumulating (precondition for momentum).

- [x] **2.1** Schema migration `migrations/0001_init.sql` (all 9 tables from TECH-PRD §2 + indexes). (M)
- [x] **2.2** RLS in same migration: anon `select`-only on every table; service-role writes bypass RLS. (S)
- [x] **2.3** `db/client.py` service-role factory (lazy supabase import) + `db/rows.py` pure builders. (S)
- [x] **2.4** `upsert_apps` (conflict on app_id) + `insert_snapshots` (idempotent on app_id,captured_at). (M)
- [x] **2.5** `insert_niche_apps` + `seed_niches`; calibration keyword set in `radar/seeds.py` (20 niches). (S)
- [x] **2.6** `insert_reviews` dedupe on (app_id, apple_review_id). (S)
- [x] **2.7** `start_run`/`finish_run` for `scrape_runs` (counts, 403s, status, notes). (S)

**LIVE:** Supabase project `mac-app-radar` (ref `lzdbridvcngmvtvstkgv`, eu-west-1) created via CLI; migration applied via `supabase db push`; `.env` populated (gitignored). All 9 tables reachable from the service client.

**AC:** ✅ live scrape of 3 niches wrote 63 apps / 63 snapshots / 63 niche_apps in **4 API calls** (3 search + 1 batched lookup), `scrape_runs` row `status=ok`, 0×403. Snapshot accumulation across days happens naturally on the daily cron (unique on app_id,captured_at).

---

## M3 — Scoring engine (build-seq #3) — ENGINE DONE ⏳ calibration needs live data

Goal: turn data into Opportunity. Calibrate against gut-check niches (PRD exit criterion).

- [x] **3.1** `demand_score` — log(total ratings) + autocomplete depth + optional google vol; renormalizes when google absent. (M)
- [x] **3.2** `competition_score` — count>floor + HHI concentration + incumbent avg quality. (M)
- [x] **3.3** `gap_score` — max unhappy-mass incumbent (high_volume × low_avg_rating) + complaint density (stubbed 0 til M6). (M)
- [x] **3.4** `monetization_score` — %paid/sub + price point + grossing presence (grossing→0 for Mac, paid ratio carries it). (M)
- [x] **3.5** `buildability_multiplier` — most-common incumbent `complexity_class`; neutral 1.0 until M6. (S)
- [x] **3.6** Gates — hard-zero on sub-floor demand / no monetization / unbuildable, before blend, with `gate_reason`. (M)
- [x] **3.7** Blend `Opportunity = (D·G·M)/max(C,floor)·B`, clamped 0–100, full `raw_inputs` on the Score. (M)
- [ ] **3.8** **Calibration harness** — needs live data (M2). ⏳ (L)

Engine: 44 tests pass. **Validated on real data** — scored 3 live niches, wrote `niche_scores`, ranking looks sane (menu-bar-calendar 8.5 > clipboard 3.3 > duplicate-finder gated on thin demand). Score step lives in `pipeline/score.py` (pull niche apps + latest snapshot → engine → upsert niche_scores).

- [ ] **3.8** **Calibration** — YOURS to drive: run the full 20-niche set at `limit=200`, compare Opportunity ranking to your gut, tune `weights.json` + the `REF_*` knobs in `subscores.py` + gate floors. The harness exists; the judgment is yours (PRD §9 exit criterion).

---

## M4 — Momentum (build-seq #4) — CODE DONE ⏳ real signal needs day-over-day data

Goal: the signal manual research can't give. Needs ≥2 days of snapshots.

- [x] **4.1** `scoring/momentum.py` — per-app Δratings/Δt from two latest snapshots, averaged to niche. Tolerant ISO parser (Postgres 5-digit fractions on py<3.11). (M)
- [x] **4.2** `normalize_momentum` min-max 0–100 across niches (None when <2 snapshots, neutral 50 on tie); written into `niche_scores.momentum` + `ratings_per_day` in raw_inputs. 11 tests. (S)
- [ ] **4.3** Retroactive validation — needs real day-over-day data (PRD §9). ⏳ (M)

**AC:** ✅ momentum populates for niches with ≥2 snapshots (uniformly 50 now — correct, intraday deltas ≈ 0); None for single-snapshot niches. Real spread + riser validation come once the cron has run multiple days.

---

## M5 — Pipeline orchestration + GitHub Actions cron (build-seq, TECH-PRD §4, §8)

Goal: zero-babysit daily run. Wire M1–M4 into one ordered pipeline.

- [x] **5.1** `pipeline/scrape.py` + `radar.run` — niche resolve → search → dedupe → batched lookup → upsert+snapshot+niche_apps → run record. Score step in `pipeline/score.py`. (Review fetch + cron still pending: 5.2–5.4.) Live-proven. (L)
- [ ] **5.2** Bounded review fetch priority (§4.4): new apps now / watched >7d / slow rotation, capped ~150 apps/run. (M)
  - Note: reviews RSS empty for Mac (M1 finding) — gap signal stays stubbed regardless, so this is low priority until/unless review data appears.
- [x] **5.3** `.github/workflows/daily-scrape.yml` — `cron: '0 6 * * *'` + `workflow_dispatch` (seed/limit inputs), concurrency guard, `timeout-minutes: 90`, secrets wired. `radar.run` now scrapes **and** scores in one pass. (S)
- [x] **5.4** Rate-limit mid-run → `status='partial'` + note, run closed cleanly, job doesn't crash (next day's rotation self-heals). Other exceptions still propagate (fail-loud). Tested. (S)

**AC:** ✅ locally `radar` runs scrape+score unattended (run 2 ok, 126 snapshots across 2 capture times). ⏳ scheduled run needs activation: push to origin + add repo secrets.

**To activate the cron (yours):**
1. `git push origin main`
2. Repo → Settings → Secrets and variables → Actions → add `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (values in your `.env`). `ANTHROPIC_API_KEY` optional until M6.
3. (optional) Actions → daily-scrape → Run workflow with `seed=true` once to load all 20 niches.

---

## M6 — LLM jobs (decoupled) (build-seq #6, TECH-PRD §6) — BUILDABILITY DONE ⏳ needs key

Goal: review→backlog + buildability. Never blocks scrape.

- [x] **6.1** `llm/client.py` — Anthropic factory, key server-side only (`require_anthropic`), lazy import, Haiku/Sonnet model ids. (S)
- [x] **6.2** Buildability tagging (`llm/buildability.py`) — Haiku, one prompt/app → `wrapper|integration|native_complex` → `apps.complexity_class`; only untagged apps; defensive label coercion. 7 tests. (M)
- [ ] **6.3** Review clustering — **deferred: Mac reviews RSS is empty (M1 finding), so there's no review data to cluster.** Revisit if review data appears. (L)
- [x] **6.4** Buildability feeds the scorer — `buildability_multiplier` already reads `complexity_class`; once apps are tagged, the next score run uses real values + the unbuildable gate bites. (Complaint density stays stubbed per 6.3.) (S)
- [x] **6.5** Decoupled Actions step (`--tag 60`) after scrape, `continue-on-error`, runs only when the key secret is set. CLI: `radar --tag [N]`. (S)

**⏳ BLOCKED on key:** add `ANTHROPIC_API_KEY` to `.env` (local) + GitHub repo secret to activate. Token-spend logging into `scrape_runs.notes` (part of 6.1) still TODO.

**AC:** ◐ tagging code + wiring done and offline-tested; live run + real buildability scores need the key.

---

## M7 — Frontend dashboard (build-seq #5, TECH-PRD §7) — SCAFFOLD DONE

Goal: legible, read-only view + instant live probe.

- [x] **7.1** Vite + React + TS + Tailwind v4 scaffold in `frontend/`. `pnpm build` clean (tsc + vite). Cloudflare Pages deploy still TODO. (S)
- [x] **7.2** Supabase JS read client (`lib/supabase.ts`, anon key from `VITE_*` env, RLS). Anon read + niches join verified live. (S)
- [x] **7.3** Niche table — sortable by every sub-score incl. Opportunity / Momentum; gated niches badged with reason tooltip. (M)
- [x] **7.4** Opportunity × Momentum scatter (`components/Scatter.tsx`, pure SVG, quadrant guides, auto-scaled Y, table/scatter toggle). Niches without momentum listed below, not dropped. (M)
- [ ] **7.5** Niche drill-down — incumbent list, per-app rating-history sparkline, version cadence, clustered unmet needs. (L)
- [ ] **7.6** **Live probe** — keyword in → JSONP iTunes call → score via TS-mirrored scoring spec (shares `weights.json`), no DB hop. (L)
- [x] **7.7** Real empty / skeleton-loading / error states; demand labeled `est.` (no false precision). (M)

**AC:** ✅ dashboard renders real DB data (3 live niches via anon key). Scatter (7.4), drill-down (7.5), live probe (7.6) still to build.

---

## M8 — Observability + watchlist/alerts (build-seq #7)

- [ ] **8.1** Health view over `scrape_runs` (counts, 403s, partial banner). (M)
- [ ] **8.2** Watchlist — mark niches; alert when momentum crosses velocity threshold. (M)
- [ ] **8.3** Alert delivery (email/webhook — pick one). (S)

**AC:** crossing a velocity threshold on a watched niche fires an alert; dashboard surfaces partial/failed runs.

---

## Liveness / "still in demand" (added — rating_count is lifetime, not current demand)

- [x] **Freshness discount** — each app's ratings weighted by `0.5^(days_since_update / half_life_days)` (config in `weights.json` `freshness`, default 365d half-life, 0.1 floor). Applied to demand + gap so abandonware stops counting as live demand. `avg_freshness` in `niche_scores.raw_inputs`. Tolerant ISO parser shared. Data showed 28% of apps >18mo stale, 19% >3yr.
- [ ] **Per-app velocity weighting** — the stronger liveness signal: weight ratings by recent Δratings/day once the cron has ≥2 days of snapshots (extends M4 to per-app, feeds demand). ⏳ needs day-over-day data.
- [ ] **Staleness display** — surface last-update age / freshness in the frontend drill-down (M7.5).

## M9 — Discovery engine (auto keyword generation) — BUILT ⏳ needs key

Goal: stop hand-seeding. Self-feeding generate → validate → auto-promote funnel (PRD open q #1, expanded).

- [x] **9.1** `niche_candidates` table + migration 0002 (applied live). (S)
- [x] **9.2** LLM generator (`llm/discover.py`) — Claude (Sonnet) proposes arbitrage-shaped keywords, given an avoid-list of already-tracked terms; defensive JSON-array parse. (M)
- [x] **9.3** Funnel (`pipeline/discover.py`) — generate → insert candidates → per-candidate search+lookup+score (budget-capped) → auto-promote `opportunity ≥ threshold` into watched `niches`, else reject with reason. Config in `weights.json` `discovery`. (L)
- [x] **9.4** CLI `radar --discover` + decoupled, key-guarded daily Actions step. (S)
- [x] **9.4b** **Manual watch via UI** — `supabase/functions/watch` Edge Function (service-role add/remove, anon-gated) + frontend Discovery tab (`Discovery.tsx`, `useCandidates`, `lib/watch.ts`) with a Track/Untrack button per candidate. Live-verified add+remove. Watch list reset to empty for fresh curation. (L)
- [ ] **9.5** App-set dedup — collapse candidates that resolve to the same competitive set (Jaccard on app-ids) so volume ≠ duplicate niches. Currently dedup is keyword-level only. (M)
- [x] **9.6** **Google Suggest generator** (`adapters/google_suggest.py` + `google_candidates`) — free, no-key, real high-volume completions (Apple's autocomplete is dead). Now the DEFAULT discovery source; LLM layered on when key present. Funnel refactored source-agnostic. Discovery Actions step no longer key-gated. (M)
- [ ] **9.7** Use Google suggestion order/presence as the demand proxy (fills the dead Apple-autocomplete signal). (S)
- [ ] **9.8** Catalog-harvest generator (n-grams from scraped titles/categories) as a third no-key source. (M)

Decisions: ~~auto-promote~~ **REVISED** → discovery fills a scored candidate POOL only; operator hand-picks what to track. `radar --watch <kw>` promotes a candidate into the watch list. Validation drains the backlog (oldest `new` first) so the pool deepens daily. Generators dropped: autocomplete (Apple dead). Live: 195 candidates from 20 google seeds, scored.

**AC:** ◐ code + wiring done, offline-tested; live discovery (real candidates promoted) needs the key. Threshold `min_opportunity_to_promote=8.0`, budget 30/day — tune in `weights.json`.

## Data backup

- [x] **Export** — `radar --export DIR` dumps all 10 tables to JSONL + manifest (paginated). Live-verified: 8445 rows. `db/export.py`.
- [x] **Weekly backup workflow** — `backup.yml` (Sun 05:00 UTC) runs export → uploads artifact (90-day retention). Supabase free tier has no guaranteed auto-backups, so this is the safety net.
- Note: raw API responses (`FileRawStore`) are local/ephemeral in CI — not backed up, but re-fetchable; the scored/snapshot data (the precious part) is covered.

## Open questions to resolve in-flight (PRD §10 / TECH §12)
- Lookup batch ceiling: 150 vs 200 (resolve in 1.4).
- Review pages-deep before diminishing returns (resolve in 1.5 / 5.2).
- US-only vs multi-storefront demand (default US for v1).
- Weights: hand-tuned vs fitted to labeled set (resolve in 3.8).
- Mac grossing feed real or commit to metadata-ratio fallback (resolve in 1.6).
- Niche input: free-text vs seeded taxonomy (affects 2.5).

---

## Suggested first sprint (smallest useful slice)
M0 → M1.1–1.4 → M2.1–2.5 → one manual end-to-end scrape of 3 niches writing snapshots. That alone validates the entire data spine before any scoring/LLM/frontend spend.
