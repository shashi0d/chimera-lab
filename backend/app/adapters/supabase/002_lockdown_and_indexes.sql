-- Run after schema.sql and 001_agent_api.sql.
--
-- 1. incr_counter keeps the daily caps. Postgres grants EXECUTE on new functions to PUBLIC, and Supabase exposes
--    public-schema functions over its REST API, so without this the publishable (anon) key could call it to raise
--    the counters (locking every visitor out) or lower them (bypassing the caps). Only the backend may call it.
--    A fixed search_path keeps the function from resolving `counters` through a caller-controlled schema.
alter function public.incr_counter(text, int) set search_path = public;
revoke execute on function public.incr_counter(text, int) from public, anon, authenticated;
grant execute on function public.incr_counter(text, int) to service_role;

-- 2. The backend lists documents by one JSON field (DbAdapter.list): assets by visitor (lab edits, jobs, finals)
--    and kind; creatures by kind (indexed in 001).
create index if not exists assets_visitor_idx on assets ((doc->>'visitor'));
create index if not exists assets_kind_idx on assets ((doc->>'kind'));
