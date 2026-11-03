-- Run after 002_lockdown_and_indexes.sql.
--
-- Newer Supabase projects no longer grant data privileges on tables created by `postgres` to the API roles: by
-- default service_role, anon and authenticated get only REFERENCES, TRIGGER and TRUNCATE (pg_default_acl for
-- postgres in schema public). The backend then fails with "permission denied for table assets" (42501).
--
-- Only the backend (service_role) reads and writes these tables. The publishable/anon key and signed-in users get
-- nothing at all, not even TRUNCATE; RLS (enabled with no policies) is the second layer.
do $$
declare t text;
begin
  foreach t in array array['assets', 'runs', 'graphs', 'creatures', 'idempotency', 'counters', 'agent_runs'] loop
    execute format('revoke all on table public.%I from anon, authenticated', t);
    execute format('grant select, insert, update, delete on table public.%I to service_role', t);
  end loop;
end $$;
