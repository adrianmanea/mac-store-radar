-- Bulk-update per-app rating velocity in one call. A partial PostgREST upsert can't be
-- used (its INSERT tuple violates apps.name NOT NULL before ON CONFLICT can UPDATE), so
-- the trends job calls this function with a JSON array and it UPDATEs matching rows only.

create or replace function set_app_velocity(updates jsonb)
returns integer
language plpgsql
as $$
declare
  n integer;
begin
  update apps a
  set ratings_per_day = (u.elem->>'ratings_per_day')::numeric,
      trend_at        = (u.elem->>'trend_at')::timestamptz
  from jsonb_array_elements(updates) as u(elem)
  where a.app_id = (u.elem->>'app_id')::bigint;
  get diagnostics n = row_count;
  return n;
end;
$$;
