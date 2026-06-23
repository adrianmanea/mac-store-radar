-- Trending: per-app rating velocity (Δratings/day) computed daily from snapshots, so the
-- UI can rank "apps getting traffic now" without recomputing over the full time-series.

alter table apps add column if not exists ratings_per_day numeric;
alter table apps add column if not exists trend_at timestamptz;

create index if not exists apps_ratings_per_day on apps (ratings_per_day desc nulls last);
create index if not exists apps_release_date on apps (release_date desc nulls last);
