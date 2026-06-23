-- M9 Discovery: generated niche candidates funnel (generate -> validate -> promote).
-- Apply via `supabase db push`.

create table if not exists niche_candidates (
  keyword          text primary key,           -- the candidate search term
  source           text not null,              -- 'llm' | 'catalog' | 'taxonomy'
  status           text not null default 'new',-- new | validated | promoted | rejected
  best_opportunity numeric,                     -- score at validation time
  n_apps           integer,
  reason           text,                        -- why rejected / promoted
  generated_at     timestamptz default now(),
  last_checked     timestamptz
);
create index if not exists niche_candidates_status on niche_candidates (status, last_checked);

alter table niche_candidates enable row level security;
drop policy if exists anon_read on niche_candidates;
create policy anon_read on niche_candidates for select to anon using (true);
