-- The Garden lists every shared creature (DbAdapter.list("assets", "garden", "public")). Optional: without it the
-- query still works, it just scans the table.
create index if not exists assets_garden_idx on assets ((doc->>'garden'));
