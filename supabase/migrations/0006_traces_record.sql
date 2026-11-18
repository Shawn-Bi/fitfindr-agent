-- Capstone (Shape B): one structured record per search, kept next to the trace row.
-- Holds query, filters, per-store status/latency/error, result count, total
-- latency, tokens and cost (backend/searchlog.py). No user id, key or listing
-- contents are ever in it. Safe to run twice.
alter table public.traces add column if not exists record jsonb;
