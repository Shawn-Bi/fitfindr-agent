import type { ConditionKey, GenderFilter, Platform, SearchFilters } from "./types";

export const EMPTY_FILTERS: SearchFilters = {
  min_price: null,
  max_price: null,
  sizes: null,
  conditions: [],
  colors: [],
  gender: null,
  within_days: null,
  stores: [],
  location: null,
};

const list = (v: string | null) => (v ? v.split(",").filter(Boolean) : []);
const num = (v: string | null) => (v != null && v !== "" && Number.isFinite(Number(v)) ? Number(v) : null);

/** URL → filters. Only what the user set explicitly is in the URL; the profile fills the rest. */
export function filtersFromParams(p: URLSearchParams): SearchFilters {
  const within = num(p.get("within"));
  const gender = p.get("gender");
  return {
    min_price: num(p.get("min")),
    max_price: num(p.get("max")),
    sizes: p.has("sizes") ? list(p.get("sizes")) : null,
    conditions: list(p.get("cond")) as ConditionKey[],
    colors: list(p.get("colors")),
    gender: gender === "women" || gender === "men" || gender === "any" ? (gender as GenderFilter) : null,
    within_days: within === 1 || within === 7 || within === 30 ? within : null,
    stores: list(p.get("stores")) as Platform[],
    location: p.get("loc") || null,
  };
}

export function filtersToParams(f: SearchFilters, p: URLSearchParams = new URLSearchParams()): URLSearchParams {
  const set = (key: string, value: string | null) => (value == null || value === "" ? p.delete(key) : p.set(key, value));
  set("min", f.min_price != null ? String(f.min_price) : null);
  set("max", f.max_price != null ? String(f.max_price) : null);
  if (f.sizes == null) p.delete("sizes");
  else p.set("sizes", f.sizes.join(","));
  set("cond", f.conditions.join(","));
  set("colors", f.colors.join(","));
  set("gender", f.gender);
  set("within", f.within_days != null ? String(f.within_days) : null);
  set("stores", f.stores.join(","));
  set("loc", f.location);
  return p;
}

/** The JSON body fields POST /search takes for these filters. */
export function filtersToBody(f: SearchFilters) {
  return {
    min_price: f.min_price,
    max_price: f.max_price,
    sizes: f.sizes,
    conditions: f.conditions,
    colors: f.colors,
    gender: f.gender,
    within_days: f.within_days,
    stores: f.stores,
    location: f.location,
  };
}

/** How many filters differ from "nothing set" (the badge on the phone Filters button). */
export function activeCount(f: SearchFilters): number {
  return [
    f.min_price != null || f.max_price != null,
    !!f.sizes?.length,
    f.conditions.length > 0,
    f.colors.length > 0,
    !!f.gender && f.gender !== "any",
    f.within_days != null,
    f.stores.length > 0,
  ].filter(Boolean).length;
}
