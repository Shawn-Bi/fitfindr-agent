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
  brand?: string | null;
  listed_at?: string | null;
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
  photo?: string | null;
}

export type ConditionKey = "new_with_tags" | "new" | "like_new" | "good" | "fair";
export type GenderFilter = "women" | "men" | "any";

/** Results-page filters (B4). sizes null = not set (the profile fills it in). */
export interface SearchFilters {
  min_price: number | null;
  max_price: number | null;
  sizes: string[] | null;
  conditions: ConditionKey[];
  colors: string[];
  gender: GenderFilter | null;
  within_days: 1 | 7 | 30 | null;
  stores: Platform[];
  /** US ZIP or city for FB Marketplace; null = the profile's (default New York, NY). */
  location: string | null;
}

export type FilterKey = "price" | "size" | "condition" | "colour" | "gender" | "listed_within" | "location" | "store";
export type FilterSupport = Record<FilterKey, { available: boolean; note?: string }>;

/** The buyer's verdict around the fit card caption (B1). Estimates are labelled, never facts. */
export interface FitVerdict {
  retail: { low: number; high: number; confidence: "high" | "medium"; pct_off: number | null; above_retail: boolean } | null;
  era: { label: string; confidence: "high" | "medium" } | null;
  brand_value: string | null;
  longevity: "classic" | "trend-driven" | "mixed" | null;
  condition: { grade: ConditionKey | null; label: string | null; stated: string | null; notes: string | null };
  verdict: "Worth it" | "Fair deal" | "Skip" | null;
  reasons: string[];
}

export interface SearchResponse {
  query: string;
  parsed: { description: string; size: string | null; sizes?: string[]; max_price: number | null; min_price?: number | null };
  filters?: Omit<SearchFilters, "gender" | "location"> & { gender: GenderFilter; sizes: string[]; location: string | null };
  filter_support?: FilterSupport;
  agent?: { planner: string; steps: string[]; ranking: string | null };
  relaxed?: { dropped: "size" | "budget"; label: string; message: string; new_max_price?: number } | null;
  /** Fewer than 4 results: what the search widened, step by step, in one line. */
  broadened?: { steps: string[]; message: string; max_price: number | null; dropped_size: boolean } | null;
  /** A filter-change search: results only; styling comes from POST /search/style. */
  styling_deferred?: boolean;
  clarify?: { question: string; suggestions: string[] } | null;
  fit_verdict?: FitVerdict | null;
  chips: Chip[];
  results: Listing[];
  stores: StoreStatus[];
  data_mode: "fixtures" | "live";
  personalized: boolean;
  signed_in: boolean;
  closet_count: number;
  profile: { sizes: Sizes; budget: number | null; budget_min?: number | null; gender?: Gender | null } | null;
  styling: { text: string | null; items: StylingItem[]; unavailable: string | null } | null;
  fit_card: string | null;
  empty: { title?: string; message: string; relax: { label: string; params: Record<string, unknown> }[] } | null;
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
  gender?: "women" | "men" | "unisex" | null;
  created_at: string;
  updated_at: string;
}

export type SizeRange = "regular" | "petite" | "plus";

/** US retail size groups (backend api/catalog.py SIZE_KEYS), several values each. */
export interface Sizes {
  size_range: SizeRange[];
  tops: string[];
  bottoms_waist: string[];
  bottoms_inseam: string[];
  shoes: string[];
  men_tops: string[];
  men_neck: string[];
  men_sleeve: string[];
  men_waist: string[];
  men_inseam: string[];
  men_shoes: string[];
}

export type Gender = "women" | "men" | "both";
export type Fit = "slim" | "regular" | "relaxed" | "oversized";

export interface Measurements {
  unit?: "in" | "cm";
  bust?: number;
  waist?: number;
  hips?: number;
  height?: number;
}

export interface Profile {
  user_id: string;
  email: string | null;
  sizes: Sizes;
  styles: string[];
  colors: string[];
  budget: number | null;
  budget_min: number | null;
  location: string;
  gender: Gender | null;
  fit: Fit | null;
  measurements: Measurements;
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

/** One planned piece of an AI-stylist outfit (B2), with a real listing only when one truly fits. */
export interface OutfitPiece {
  slot: "top" | "bottom" | "outerwear" | "shoes" | "bag";
  category: Category;
  label: string;
  name: string;
  colors: string[];
  material: string | null;
  search: string;
  why: string | null;
  /** listing = passed the strict check; closest = closest real listing; ai_preview = generated picture; idea = swatches only. */
  kind?: "listing" | "closest" | "ai_preview" | "idea";
  listing: Listing | null;
  found_at: string | null;
  match_reason: string | null;
  closest_note?: string | null;
  preview_url?: string | null;
  expired?: boolean;
}

export interface StyleResponse {
  styling: { text: string | null; items: StylingItem[]; unavailable: string | null };
  fit_card: string | null;
  fit_verdict: FitVerdict | null;
}

export interface Outfit {
  title: string;
  concept: string | null;
  palette: string[];
  occasion: string | null;
  notes: { colour: string | null; proportion: string | null; fabric: string | null };
  planner: "gemini" | "template";
  styles: string[];
  default_style: boolean;
  pieces: OutfitPiece[];
  generated_at: string;
  data_mode: "fixtures" | "live";
}

export interface OutfitResponse {
  status: "none" | "pending" | "ready" | "failed";
  outfit: Outfit | null;
  stale: boolean;
  item_photo: string | null;
  updated_at?: string;
}

export interface AutoTagSuggestion {
  name: string | null;
  category: Category | null;
  colors: string[];
  style_tags: string[];
  season: string[];
  gender: "women" | "men" | "unisex" | null;
}
