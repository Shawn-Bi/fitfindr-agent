-- v2 fixes: a US ZIP or city per profile, for Facebook Marketplace searches
-- (local pickup). Empty means the default, New York, NY.
alter table public.profiles add column if not exists location text;
