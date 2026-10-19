-- FitFindr database schema (PRD v2.2, section 7).
-- Paste into Supabase → SQL Editor → Run. Safe to re-run.
--
-- User tables (profiles, closet_items, saved_items): row-level security so each
-- signed-in user can only read and write their own rows.
-- Server tables (api_usage, search_cache): RLS on with NO policies, so only the
-- backend (service role key, which bypasses RLS) can touch them.
-- "users" is Supabase's built-in auth.users table; we don't create our own.

-- ─── profiles ────────────────────────────────────────────────────────────────
create table if not exists public.profiles (
  user_id      uuid primary key references auth.users (id) on delete cascade,
  sizes        jsonb   not null default '{}'::jsonb,  -- {"top":"M","waist":"30","length":"32","shoe":"US 9"}
  styles       text[]  not null default '{}',
  colors       text[]  not null default '{}',
  budget       numeric(10, 2) check (budget is null or budget >= 0),  -- USD per item
  email_opt_in boolean not null default false,        -- "Email me new matches" (recorded only)
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- Create an empty profile automatically when someone signs up.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (user_id) values (new.id) on conflict do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ─── closet_items ────────────────────────────────────────────────────────────
create table if not exists public.closet_items (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  photo_url   text not null,          -- path in the private closet-photos bucket: <user_id>/<file>
  name        text not null check (length(trim(name)) > 0),
  category    text not null check (category in
                ('tops', 'bottoms', 'outerwear', 'dresses', 'shoes', 'accessories')),
  colors      text[] not null check (cardinality(colors) > 0),
  style_tags  text[] not null default '{}',
  size        text,
  brand       text,
  season      text[] not null default '{}',
  notes       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists closet_items_user_idx on public.closet_items (user_id, category);

-- ─── saved_items ─────────────────────────────────────────────────────────────
create table if not exists public.saved_items (
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  listing_id  text not null,           -- the platform's own listing id
  source      text not null,           -- depop | poshmark | mercari | etsy | ebay | fb_marketplace
  listing     jsonb,                   -- snapshot of the standard listing dict, for the Saved page
  available   boolean not null default true,  -- false → "No longer available"
  saved_at    timestamptz not null default now(),
  primary key (user_id, source, listing_id)
);

-- ─── api_usage (server only) ─────────────────────────────────────────────────
-- One row per RapidAPI host per calendar month. A new month is a new row,
-- which is how the count "resets on the 1st".
create table if not exists public.api_usage (
  host   text not null,
  month  date not null,                -- first day of the month, e.g. 2026-10-01
  count  integer not null default 0 check (count >= 0),
  primary key (host, month)
);

-- Atomically add one call and return the new count (backend calls this via RPC).
create or replace function public.increment_api_usage(p_host text)
returns integer language sql security definer set search_path = public as $$
  insert into public.api_usage (host, month, count)
  values (p_host, date_trunc('month', now() at time zone 'utc')::date, 1)
  on conflict (host, month) do update set count = public.api_usage.count + 1
  returning count;
$$;
revoke all on function public.increment_api_usage(text) from public, anon, authenticated;

-- ─── search_cache (server only) ──────────────────────────────────────────────
-- Real API responses, reused for at most 24 hours.
create table if not exists public.search_cache (
  query_hash     text not null,
  platform       text not null,
  response_json  jsonb not null,
  fetched_at     timestamptz not null default now(),
  primary key (query_hash, platform)
);
create index if not exists search_cache_fetched_idx on public.search_cache (fetched_at);

-- ─── updated_at bookkeeping ──────────────────────────────────────────────────
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_touch on public.profiles;
create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();

drop trigger if exists closet_items_touch on public.closet_items;
create trigger closet_items_touch before update on public.closet_items
  for each row execute function public.touch_updated_at();

-- ─── Row-level security ──────────────────────────────────────────────────────
alter table public.profiles     enable row level security;
alter table public.closet_items enable row level security;
alter table public.saved_items  enable row level security;
alter table public.api_usage    enable row level security;   -- no policies: server only
alter table public.search_cache enable row level security;   -- no policies: server only

drop policy if exists "own profile" on public.profiles;
create policy "own profile" on public.profiles
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own closet items" on public.closet_items;
create policy "own closet items" on public.closet_items
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own saved items" on public.saved_items;
create policy "own saved items" on public.saved_items
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ─── Storage: private bucket closet-photos ───────────────────────────────────
-- Create the bucket in the dashboard (Storage → New bucket → closet-photos,
-- Public OFF). Files go under <user_id>/..., and each user can only touch
-- files in their own folder.
drop policy if exists "closet photos: own folder read" on storage.objects;
create policy "closet photos: own folder read" on storage.objects
  for select to authenticated
  using (bucket_id = 'closet-photos' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "closet photos: own folder insert" on storage.objects;
create policy "closet photos: own folder insert" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'closet-photos' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "closet photos: own folder update" on storage.objects;
create policy "closet photos: own folder update" on storage.objects
  for update to authenticated
  using (bucket_id = 'closet-photos' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "closet photos: own folder delete" on storage.objects;
create policy "closet photos: own folder delete" on storage.objects
  for delete to authenticated
  using (bucket_id = 'closet-photos' and (storage.foldername(name))[1] = auth.uid()::text);
