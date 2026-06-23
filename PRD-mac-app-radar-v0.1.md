# PRD — Mac App Opportunity Radar (working name)

**Version:** v0.1
**Owner:** Adrian
**Status:** Draft for review
**One-liner:** A tool that scans the Mac App Store for under-served niches with proven demand and weak incumbents, and scores each on whether it's worth building.

---

## 1. Problem & opportunity

App Store SEO arbitrage works when you find an existing search demand whose incumbents are weak, monetizing, and beatable. Today that discovery is fully manual: querying the iTunes API by hand, eyeballing rating counts, reading reviews one app at a time, and holding the competitive picture in your head. It doesn't scale, it has no memory (so you can't see what's *rising*), and the judgment ("is this worth building?") lives only in intuition.

The opportunity is to automate the exact workflow we've been running by hand — competitive set → metadata → review-gap mining → a defensible score — and add the one thing manual research can't give you: **change over time** (momentum), so you catch a category while it's emerging rather than after it's saturated.

This is an **arbitrage radar, not a greenfield idea generator.** It surfaces existing demand with weak incumbents. That's the actual strategy, so that's the scope.

## 2. Goals / Non-goals

**Goals**
- Score any niche/keyword on demand, competition, gap, monetization, and buildability in one view.
- Track rating velocity over time to flag emerging winners (the DroidSync case — catch it before it ranks).
- Mine recent reviews into a clustered list of unmet needs per app, so a "what would I build" backlog falls out automatically.
- Make the score legible: every number traceable to its inputs, no black box.

**Non-goals (v1)**
- Not a paid-data replacement for Sensor Tower / Appfigures (we proxy, we don't license install data).
- Not an idea generator for categories with zero existing demand.
- Not iOS-first. Mac App Store is the wedge (smaller, weaker incumbents, your existing focus). iOS is a later toggle.
- Not multi-user/SaaS in v1 — single-operator tool first, productize only if the scores prove themselves.

## 3. Target user

Primary: you — a solo indie/design-engineer hunting Mac build targets.
Secondary (later, if productized): other indie Mac/iOS devs doing ASO arbitrage. The micro-SaaS angle is real but gated behind v1 proving the model works.

## 4. Core concept — how the score works

Two outputs, not one number, because they answer different questions:

- **Opportunity** — is this niche worth entering *at all*? A blend of demand, gap, and monetization, divided by competition, multiplied by a buildability factor.
- **Momentum** — is it heating up *right now*? Normalized rating velocity across the niche.

Plot niches on **Opportunity × Momentum**:
- High opportunity + high momentum → act now.
- High opportunity + flat momentum → stable cash cow nobody's contesting (often the *better* arbitrage — less risk of a land-grab).
- Low opportunity → ignore regardless of momentum.

### Sub-scores (each normalized 0–100)

- **Demand (D)** — log(total ratings across the niche) + web search volume for "<thing> mac" + App Store autocomplete depth. Answers: do people want this?
- **Competition (C)** — count of incumbents above a rating floor, *plus concentration* (one 50k-rating gorilla = category locked) *plus incumbent quality* (high average rating = hard to unseat).
- **Gap (G)** — the money signal. `high_volume × low_avg_rating` = many unhappy users, plus complaint density from review mining. Lots of 2-star reviews on a high-traffic app is the whole thesis.
- **Monetization (M)** — % of incumbents that are paid/subscription, their price points, and top-grossing-chart presence (proven willingness to pay).
- **Buildability (B)** — complexity class, LLM-tagged from app descriptions: API-wrapper = high, Finder/MTP-style integration = medium, complex-native = low.

### Formulas (v0.1 — to be calibrated)

```
Opportunity = ( D · G · M ) / C  ·  B_multiplier
Momentum    = normalize( Δ ratings / Δ time, across niche )
```

### Gates (applied before the blend — hard zeros)

A niche scores zero regardless of other signals if:
- No provable monetization (no paid/subscription/grossing incumbents), OR
- Buildability below threshold (can't ship it solo in a reasonable window), OR
- Demand under a floor (too small to matter).

Gates first, weighted blend second. This stops the model from recommending unbuildable or unmonetizable niches that happen to score high on raw demand.

## 5. Data sources & signals

| Signal | Source | Cost | Notes |
|---|---|---|---|
| Competitive set per niche | iTunes Search API (`entity=macSoftware`) | Free | Up to 50 apps/keyword in one call |
| Per-app metadata | iTunes Lookup API | Free | ratings count, avg rating, price, IAP, release dates, category |
| Review/gap mining | iTunes customer-reviews RSS (JSON) | Free | **Recent reviews only**, ~500 max/app — enough for gap signal |
| Proven monetization | App Store top-grossing/paid chart feeds | Free | **Mac feeds are flaky — verify endpoint form at build time** |
| Demand proxy | App Store search autocomplete + Google Keyword Planner | Free | Autocomplete endpoint is unofficial; may break |
| Momentum | Daily snapshots of rating counts (self-collected) | Infra | The only signal that requires persistence |
| Review clustering + buildability tagging | Claude API | ~$ | LLM does the unmet-need clustering and complexity class |

### The one genuinely hard signal

Apple exposes **no true App Store search volume.** Everything else is a direct read; demand is the only estimate. We triangulate (autocomplete depth + Google web volume + aggregate niche ratings) and label it explicitly as an estimate in the UI. Don't pretend it's measured.

## 6. Scope — phased

### Phase 0 — Validation (stateless scorer)
Prove the scoring model matches your intuition before building any infrastructure.
- Single keyword in → competitive set, sub-scores, Opportunity number out.
- No momentum (no history yet), no DB.
- Gap mining optional/manual at this stage.
- **Exit criterion:** you run 15–20 niches you already have a gut read on, and the scores broadly agree. If they don't, recalibrate weights before spending on infra.

### Phase 1 — The real tool (adds memory)
- Daily snapshot scraper → time-series store → **Momentum** goes live.
- Automated review mining → clustered unmet-need backlog per niche.
- Dashboard: niche list, Opportunity × Momentum scatter, drill-down per app with reviews + version cadence.
- Watchlist + alerts ("X crossed velocity threshold").

### Phase 2 — Productize (only if Phase 1 earns it)
- Multi-user, auth, saved searches, billing.
- iOS toggle.
- Shareable niche reports.

## 7. Technical architecture — the decision

### The crux

The tool splits cleanly into two jobs:
1. **Stateless scoring** — can run entirely client-side. The iTunes Search/Lookup API supports a JSONP `callback` param, so a static frontend can call it directly with no backend and no CORS proxy.
2. **Momentum** — fundamentally requires persistent daily snapshots. This is what forces a backend. There is no way around it: "trending" needs history, and history needs storage + a scheduler.

So the architecture question is really just *"how do I run a daily scrape and store time-series cheaply, with minimal ops?"*

### Recommendation

**Frontend:** Vite + React static SPA (your existing comfort zone), hosted on Cloudflare Pages or Vercel. Phase 0 ships as frontend-only.

**Scraper runtime:** **Python on a GitHub Actions scheduled workflow.** This is the key call — it gives you free scheduled compute, keeps scraping in Python (where you're already fluent from the email-parsing project), and means **zero servers to babysit.** The Action runs daily, hits the iTunes APIs, writes snapshots to the DB.

**Storage + API:** **Supabase (managed Postgres).** Postgres is the right shape for time-series velocity queries, Supabase gives you a hosted DB + auto-generated REST/RPC API + auth-for-free if you productize later, all at near-zero ops and a free tier that covers Phase 1.

**LLM:** Claude API called from a thin serverless function (Supabase Edge Function or a Cloudflare Worker) that holds the key server-side — never ship the key in the SPA.

```
[GitHub Actions cron]  ──daily──>  Python scraper  ──>  Supabase (Postgres)
                                                              │
[Vite/React SPA]  <──REST/RPC──  Supabase  <──reads──────────┘
       │
       └──live JSONP calls──>  iTunes Search/Lookup (Phase 0 + on-demand)
       └──> serverless fn ──> Claude API (review clustering, buildability)
```

### Why not the alternatives

- **Pure in-browser, no backend:** great for Phase 0, but can never do momentum (no persistence) and exposes you to client-side rate limits. Use it to validate, not as the destination.
- **Cloudflare Workers + D1 + Cron Triggers:** genuinely good and cheapest at scale; the edge stack is tidy. Downside: D1 (SQLite) is younger, time-series/window queries are nicer in Postgres, and you'd write the scraper in JS/TS instead of Python. Pick this only if you want everything on one Cloudflare bill and don't mind TS scraping.
- **Self-hosted VPS + Python cron + SQLite + FastAPI:** maximum control, no vendor lock-in, but it's the most ops (you own uptime, backups, the box). Not worth it for a solo tool when GitHub Actions + Supabase removes all of it.

### Decision summary

> **Vite/React SPA + Python scraper on GitHub Actions cron + Supabase Postgres + Claude via a serverless proxy.** Lowest ops, keeps scraping in Python, time-series-friendly, free-tier-friendly, and productizable later without a rewrite.

## 8. Key technical risks & mitigations

- **iTunes rate limit (~20 req/min):** hard-cache every response, dedupe app IDs across niches, back off and queue. The daily scraper batches; never hammer live.
- **No true search volume:** proxy + label as estimate. Don't oversell precision.
- **Mac chart feeds unreliable:** verify the current endpoint at build; if grossing data is missing for Mac, fall back to paid/subscription ratio from metadata as the monetization signal.
- **Autocomplete endpoint is unofficial:** isolate it behind one adapter so a break is a one-file fix, not a tool-wide failure.
- **Rating count is a lagging, noisy install proxy:** review-prompt aggressiveness varies per app. Calibrate against a few apps where you can sanity-check; treat absolutes with suspicion, trust *relative* and *velocity* more than raw counts.
- **Apple ToS / scraping posture:** these are public, documented APIs intended for affiliate/search use; stay within rate limits and don't redistribute raw data if you productize. Revisit ToS before any commercial launch.

## 9. Success metrics

- **Phase 0:** scoring model agrees with your gut on ≥70% of a 15–20 niche calibration set.
- **Phase 1:** the tool surfaces at least one niche you hadn't already found by hand that survives your manual due-diligence. (One real, non-obvious lead = the tool paid for itself.)
- **Momentum validation:** retroactively, does the velocity signal flag a known riser (e.g. an Android-transfer-style app) before it hits the top of its category search results?

## 10. Open questions

- Niche input model: free-text keyword only, or a seeded taxonomy of "<google service> mac", "<android thing> mac", etc. that auto-expands?
- How many review pages deep is worth mining per app before diminishing returns on the gap signal?
- Do we weight US-store only (cleaner, your focus) or blend top storefronts for demand (more signal, more noise, more API calls)?
- Calibration: hand-tune the sub-score weights, or fit them against a small labeled set of niches you score manually?
- Where's the line for the Phase 2 productize decision — what would the tool have to show you first?
