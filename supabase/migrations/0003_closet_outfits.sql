-- v2 AI stylist (B2): one saved outfit per closet item, rebuilt when the item
-- is added or edited, so P8 can show it instantly.
create table if not exists public.closet_outfits (
  item_id       uuid primary key references public.closet_items (id) on delete cascade,
  user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  status        text not null default 'pending' check (status in ('pending', 'ready', 'failed')),
  outfit        jsonb,                -- plan + pieces (+ listing snapshots), see backend/stylist.py
  data_mode     text not null default 'fixtures' check (data_mode in ('fixtures', 'live')),
  item_version  timestamptz,          -- closet_items.updated_at the outfit was built from
  error         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists closet_outfits_user_idx on public.closet_outfits (user_id);

drop trigger if exists closet_outfits_touch on public.closet_outfits;
create trigger closet_outfits_touch before update on public.closet_outfits
  for each row execute function public.touch_updated_at();

alter table public.closet_outfits enable row level security;

drop policy if exists "own closet outfits" on public.closet_outfits;
create policy "own closet outfits" on public.closet_outfits
  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
