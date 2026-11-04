-- R1 agent API. Run after schema.sql, in the Supabase SQL editor (or `supabase db push`).
-- Adds only what schema.sql lacks:
--   1. agent_runs: one row per agent run (snapshot plus its stored SSE events), same key -> jsonb shape as the
--      other collections. Creatures reuse the existing `creatures` table (doc->>'kind' = 'evo_agent').
--   2. a PUBLIC storage bucket for generated images (renders, edits, anatomy overlays, showcase images), so the
--      gallery loads them straight from the bucket's public URL. Writes go only through the backend's service key.
-- Uploaded photos are never stored (they are only identified), so nothing private goes in this bucket.

create table if not exists agent_runs (key text primary key, doc jsonb not null);
create index if not exists agent_runs_status_idx on agent_runs ((doc->>'status'));
alter table agent_runs enable row level security;  -- no policies: the anon key reads and writes nothing

-- Gallery listing filters creatures by kind.
create index if not exists creatures_kind_idx on creatures ((doc->>'kind'));

-- Public bucket (name = EVO_PUBLIC_BUCKET, default chimera-public): public read through
-- /storage/v1/object/public/chimera-public/<key>; 10 MB per object; images only.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('chimera-public', 'chimera-public', true, 10485760, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update set public = true, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- storage.objects has row level security on. We add no insert, update or delete policy for anon or authenticated,
-- so only the service role (which bypasses RLS) can write; public reads need no policy on a public bucket.
-- Drop any broad write policy someone may have added on this bucket by hand:
drop policy if exists "chimera public write" on storage.objects;
