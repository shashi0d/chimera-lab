-- Run after 003_table_grants.sql.
-- The Lab lists a signed-in user's versions and edit jobs by owner (DbAdapter.list("assets", "owner", ...)).
create index if not exists assets_owner_idx on assets ((doc->>'owner'));
