import type { Platform } from "./types";

export const STORE_LABELS: Record<Platform, string> = {
  ebay: "eBay",
  etsy: "Etsy",
  depop: "Depop",
  poshmark: "Poshmark",
  mercari: "Mercari",
  fb_marketplace: "FB Marketplace",
};

export const STYLES = ["Vintage", "Y2K", "Streetwear", "Minimalist", "Grunge", "Cottagecore"] as const;

// Style card colors from the Home prototype (white text passes 4.5:1 on each).
export const STYLE_COLORS: Record<string, string> = {
  Vintage: "#A9502A",
  Y2K: "#B4477A",
  Streetwear: "#1B1E1C",
  Minimalist: "#4F5551",
  Grunge: "#5E6B4A",
  Cottagecore: "#7A5C3E",
};

export const CATEGORIES = [
  { key: "tops", label: "Tops" },
  { key: "bottoms", label: "Bottoms" },
  { key: "outerwear", label: "Outerwear" },
  { key: "dresses", label: "Dresses" },
  { key: "shoes", label: "Shoes" },
  { key: "accessories", label: "Accessories" },
] as const;

export const COLOR_SWATCHES: { name: string; hex: string }[] = [
  { name: "black", hex: "#1B1E1C" },
  { name: "white", hex: "#FFFFFF" },
  { name: "cream", hex: "#F3EAD7" },
  { name: "grey", hex: "#8C918D" },
  { name: "navy", hex: "#1F2F55" },
  { name: "denim blue", hex: "#34507A" },
  { name: "light blue", hex: "#A9C8E8" },
  { name: "brown", hex: "#6B4A2F" },
  { name: "camel", hex: "#C19A6B" },
  { name: "rust", hex: "#A9502A" },
  { name: "red", hex: "#B3261E" },
  { name: "pink", hex: "#E4A3B4" },
  { name: "lilac", hex: "#C8B6E2" },
  { name: "yellow", hex: "#E9C84A" },
  { name: "olive", hex: "#6B7340" },
  { name: "green", hex: "#3E7C4F" },
];

export function money(value: number): string {
  return Number.isInteger(value) ? `$${value}` : `$${value.toFixed(2)}`;
}

export function shortDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function timeAgo(iso: string | null): string | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `on ${shortDate(iso)}`;
}

/** First line of a seller title, without hashtags, emoji clutter or extra spaces. */
export function cleanTitle(title: string): string {
  const firstLine = title.split(/\n/)[0];
  const noTags = firstLine.replace(/(^|\s)#[\w-]+/g, " ");
  return noTags.replace(/\s+/g, " ").trim() || title.trim();
}

/** "M · good · Depop". With noteMissingSize, a listing without a size says so (a size filter is on). */
export function listingMeta(
  l: { size: string | null; condition: string | null; platform: Platform },
  noteMissingSize = false,
) {
  const size = l.size ?? (noteMissingSize ? "size not listed" : null);
  return [size, l.condition, STORE_LABELS[l.platform]].filter(Boolean).join(" · ");
}
