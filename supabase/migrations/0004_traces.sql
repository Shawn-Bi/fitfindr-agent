-- v2 observability (A2): one row per agent run (search, stylist, auto-tag).
-- Server only: RLS on with no policies, written and read with the service key.
-- Rows are deleted with the user (cascade) and are meant for debugging only.
create table if not exists public.traces (
  id             uuid primary key default gen_random_uuid(),
  created_at     timestamptz not null default now(),
  user_id        uuid references auth.users (id) on delete cascade,   -- null for guests
  kind           text not null default 'search',                       -- search | stylist | autotag
  query          text,
  planner        text,                                                 -- gemini | rules
  outcome        text,                                                 -- completed | empty | clarify | relaxed | error
  steps          jsonb not null default '[]'::jsonb,
  tool_calls     integer not null default 0,
  model_calls    integer not null default 0,
  latency_ms     integer not null default 0,
  prompt_tokens  integer not null default 0,
  output_tokens  integer not null default 0,
  est_cost_usd   numeric(12, 6) not null default 0
);
create index if not exists traces_created_idx on public.traces (created_at desc);

alter table public.traces enable row level security;   -- no policies: server only
