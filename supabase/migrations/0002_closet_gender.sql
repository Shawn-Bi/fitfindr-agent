-- v2 closet items (A3, B2): who the piece is cut for. Filled from the photo
-- auto-tagger or the profile; used so a women's closet never gets men's finds.
alter table public.closet_items
  add column if not exists gender text
    check (gender is null or gender in ('women', 'men', 'unisex'));
