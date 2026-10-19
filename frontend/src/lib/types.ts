export type Platform = "ebay" | "etsy" | "depop" | "poshmark" | "mercari" | "fb_marketplace";

export interface Listing {
  id: string;
  title: string;
  price: number;
  size: string | null;
  platform: Platform;
  url: string;
  image_url: string | null;
  condition: string | null;
  updated_at: string | null;
  category: string | null;
  saved?: boolean;
}

export interface StoreStatus {
  platform: Platform;
  label: string;
  status: "live" | "paused" | "coming_soon" | "error";
  count: number;
  resumes?: string;
}

export interface Chip {
  key: "q" | "size" | "price";
  label: string;
  from_profile: boolean;
}

export interface StylingItem {
  id: string;
  name: string;
  category: string;
  thumb: string | null;
}

export interface SearchResponse {
  query: string;
  parsed: { description: string; size: string | null; max_price: number | null };
  chips: Chip[];
  results: Listing[];
  stores: StoreStatus[];
  data_mode: "fixtures" | "live";
  personalized: boolean;
  signed_in: boolean;
  closet_count: number;
  profile: { sizes: Sizes; budget: number | null } | null;
  styling: { text: string | null; items: StylingItem[]; unavailable: string | null } | null;
  fit_card: string | null;
  empty: { message: string; relax: { label: string; params: Record<string, unknown> }[] } | null;
}

export type Category = "tops" | "bottoms" | "outerwear" | "dresses" | "shoes" | "accessories";

export interface ClosetItem {
  id: string;
  user_id: string;
  photo_url: string;
  photo: string | null;
  thumb: string | null;
  name: string;
  category: Category;
  colors: string[];
  style_tags: string[];
  size: string | null;
  brand: string | null;
  season: string[];
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Sizes {
  top?: string;
  waist?: string;
  length?: string;
  shoe?: string;
}

export interface Profile {
  user_id: string;
  email: string | null;
  sizes: Sizes;
  styles: string[];
  colors: string[];
  budget: number | null;
  email_opt_in: boolean;
  onboarded: boolean;
}

export interface Pick {
  listing: Listing;
  reason: string | null;
}

export interface SavedRow {
  listing_id: string;
  source: Platform;
  listing: Listing | null;
  available: boolean;
  saved_at: string;
}
