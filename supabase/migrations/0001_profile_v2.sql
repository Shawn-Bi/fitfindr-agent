-- v2 profile (B3): who you shop for, fit, optional body measurements and a
-- budget range. Sizes stay in the existing `sizes` jsonb, now with lists per
-- category: {"tops":["M","8"],"bottoms_waist":["28"],"bottoms_inseam":["30"],
-- "bottoms":["S"],"dresses":["6"],"shoes":["8","8.5"]}. The old single keys
-- (top, waist, length, shoe) are still read by the backend.
alter table public.profiles
  add column if not exists gender text
    check (gender is null or gender in ('women', 'men', 'both'));

alter table public.profiles
  add column if not exists fit text
    check (fit is null or fit in ('slim', 'regular', 'relaxed', 'oversized'));

-- {"unit":"in"|"cm","bust":34,"waist":27,"hips":37,"height":65} — all optional.
alter table public.profiles
  add column if not exists measurements jsonb not null default '{}'::jsonb;

-- `budget` (existing) is the max per item; budget_min is the low end of the range.
alter table public.profiles
  add column if not exists budget_min numeric(10, 2)
    check (budget_min is null or budget_min >= 0);
