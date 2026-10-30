-- Chimera Lab tables for Supabase (P7-03). Run in the SQL editor.
-- Each collection is a simple key -> jsonb document table, matching the local SQLite adapter.

create table if not exists assets      (key text primary key, doc jsonb not null);
create table if not exists runs        (key text primary key, doc jsonb not null);
create table if not exists graphs      (key text primary key, doc jsonb not null);
create table if not exists creatures   (key text primary key, doc jsonb not null);
create table if not exists idempotency (key text primary key, doc jsonb not null);
create table if not exists counters    (key text primary key, doc jsonb not null);

create index if not exists runs_status_idx on runs ((doc->>'status'));

-- Atomic counter used by the daily generation cap.
create or replace function incr_counter(k text, by int) returns int
language plpgsql as $$
declare v int;
begin
  insert into counters(key, doc) values (k, jsonb_build_object('value', by))
  on conflict (key) do update set doc = jsonb_build_object('value', (counters.doc->>'value')::int + by)
  returning (doc->>'value')::int into v;
  return v;
end $$;

-- The backend uses the service key; keep RLS on so the anon key can read nothing.
alter table assets enable row level security;
alter table runs enable row level security;
alter table graphs enable row level security;
alter table creatures enable row level security;
alter table idempotency enable row level security;
alter table counters enable row level security;

-- Storage: create a private bucket named by STORAGE_BUCKET (default chimera-assets).
insert into storage.buckets (id, name, public) values ('chimera-assets', 'chimera-assets', false)
on conflict (id) do nothing;
