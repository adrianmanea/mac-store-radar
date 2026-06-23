-- Mac App Opportunity Radar — initial schema (M2.1) + RLS (M2.2).
-- Source of truth: TECH-PRD §2. Apply to Supabase via the SQL editor or `supabase db push`.

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table if not exists apps (
  app_id              bigint primary key,        -- iTunes trackId
  bundle_id           text,
  name                text not null,
  developer_id        bigint,
  developer_name      text,
  category            text,
  price               numeric,
  currency            text,
  has_iap             boolean,
  is_subscription     boolean,
  release_date        timestamptz,
  current_ver_date    timestamptz,
  description         text,
  complexity_class    text,                      -- LLM-tagged (M6): wrapper|integration|native_complex
  complexity_at       timestamptz,
  first_seen          timestamptz default now(),
  last_seen           timestamptz default now()
);

create table if not exists app_snapshots (
  id             bigserial primary key,
  app_id         bigint references apps(app_id),
  captured_at    timestamptz not null,
  rating_count   integer,
  avg_rating     numeric,
  price          numeric,
  version        text,
  chart_rank     integer,
  unique (app_id, captured_at)
);
create index if not exists app_snapshots_app_time on app_snapshots (app_id, captured_at desc);

create table if not exists niches (
  id           bigserial primary key,
  keyword      text not null unique,
  display_name text,
  storefront   text default 'us',
  is_watched   boolean default true,
  created_at   timestamptz default now()
);

create table if not exists niche_apps (
  niche_id      bigint references niches(id),
  app_id        bigint references apps(app_id),
  search_rank   integer,
  captured_at   timestamptz not null,
  primary key (niche_id, app_id, captured_at)
);

create table if not exists niche_scores (
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
  gated_out     boolean default false,
  gate_reason   text,
  raw_inputs    jsonb,
  unique (niche_id, captured_at)
);

create table if not exists reviews (
  id              bigserial primary key,
  app_id          bigint references apps(app_id),
  apple_review_id text,
  rating          integer,
  title           text,
  body            text,
  author          text,
  submitted_at    timestamptz,
  fetched_at      timestamptz default now(),
  unique (app_id, apple_review_id)
);

create table if not exists unmet_needs (
  id            bigserial primary key,
  app_id        bigint references apps(app_id),
  theme         text,
  frequency     integer,
  severity      text,
  example_ids   jsonb,
  generated_at  timestamptz default now()
);

create table if not exists demand_signals (
  niche_id           bigint references niches(id),
  autocomplete_depth integer,
  google_volume      integer,
  captured_at        timestamptz not null,
  primary key (niche_id, captured_at)
);

create table if not exists scrape_runs (
  id            bigserial primary key,
  started_at    timestamptz default now(),
  finished_at   timestamptz,
  status        text,                             -- ok|partial|failed
  apps_seen     integer,
  apps_new      integer,
  api_calls     integer,
  http_403s     integer,
  notes         text
);

-- ---------------------------------------------------------------------------
-- RLS (M2.2): SPA uses the anon key and may only READ. All writes go through
-- the service-role key (Actions secret), which bypasses RLS entirely.
-- ---------------------------------------------------------------------------

do $$
declare t text;
begin
  foreach t in array array[
    'apps','app_snapshots','niches','niche_apps','niche_scores',
    'reviews','unmet_needs','demand_signals','scrape_runs'
  ] loop
    execute format('alter table %I enable row level security;', t);
    execute format(
      'drop policy if exists anon_read on %I;', t
    );
    execute format(
      'create policy anon_read on %I for select to anon using (true);', t
    );
  end loop;
end $$;
