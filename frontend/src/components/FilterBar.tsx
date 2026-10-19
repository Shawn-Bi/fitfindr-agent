"use client";

import { useEffect, useId, useRef, useState } from "react";
import { activeCount, EMPTY_FILTERS } from "@/lib/filters";
import { COLOR_SWATCHES, CONDITIONS, money, SIZE_OPTIONS, STORE_LABELS, US_STATES } from "@/lib/format";
import type { FilterKey, FilterSupport, Platform, SearchFilters } from "@/lib/types";
import { Swatch, ToggleChip, toggle } from "./Chips";

const LIVE_STORES: Platform[] = ["ebay", "depop", "poshmark", "mercari"];
const SOON_STORES: Platform[] = ["etsy", "fb_marketplace"];
const WITHIN = [
  { value: 1, label: "24 h" },
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
] as const;

// Used when the API hasn't said yet (Home, before any search). Same as backend FILTER_SUPPORT.
export const DEFAULT_SUPPORT: FilterSupport = {
  price: { available: true },
  size: { available: true, note: "eBay listings don't state a size." },
  condition: { available: true, note: "Matched on the condition each store states." },
  colour: { available: true, note: "Matched on colours named in the listing title." },
  gender: { available: true, note: "Matched on Men's / Women's in the title." },
  listed_within: { available: true, note: "Only Poshmark shares listing dates; other stores' items are hidden while this is on." },
  location: { available: false, note: "Not available for these stores." },
  store: { available: true },
};

const ORDER: { key: FilterKey; label: string }[] = [
  { key: "price", label: "Price" },
  { key: "size", label: "Size" },
  { key: "condition", label: "Condition" },
  { key: "colour", label: "Colour" },
  { key: "gender", label: "Gender" },
  { key: "listed_within", label: "Listed within" },
  { key: "location", label: "Location" },
  { key: "store", label: "Store" },
];

function summary(key: FilterKey, f: SearchFilters): string | null {
  switch (key) {
    case "price":
      if (f.min_price != null && f.max_price != null) return `${money(f.min_price)}–${money(f.max_price)}`;
      if (f.max_price != null) return `under ${money(f.max_price)}`;
      if (f.min_price != null) return `over ${money(f.min_price)}`;
      return null;
    case "size":
      return f.sizes?.length ? f.sizes.join(", ") : null;
    case "condition":
      return f.conditions.length === 1
        ? CONDITIONS.find((c) => c.key === f.conditions[0])?.label || null
        : f.conditions.length
          ? `${f.conditions.length} selected`
          : null;
    case "colour":
      return f.colors.length === 1 ? f.colors[0] : f.colors.length ? `${f.colors.length} colours` : null;
    case "gender":
      return f.gender === "women" ? "Women's" : f.gender === "men" ? "Men's" : null;
    case "listed_within":
      return WITHIN.find((w) => w.value === f.within_days)?.label || null;
    case "store":
      return f.stores.length === 1 ? STORE_LABELS[f.stores[0]] : f.stores.length ? `${f.stores.length} stores` : null;
    default:
      return null;
  }
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-xs font-bold text-muted">{label}</div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

/** The editor for one filter, used in both the desktop popover and the phone sheet. */
function Section({
  k,
  draft,
  setDraft,
  support,
}: {
  k: FilterKey;
  draft: SearchFilters;
  setDraft: (f: SearchFilters) => void;
  support: FilterSupport;
}) {
  const id = useId();
  const note = support[k]?.note;
  const sizes = draft.sizes || [];
  const setSizes = (v: string) => setDraft({ ...draft, sizes: toggle(sizes, v) });
  let body: React.ReactNode = null;

  if (k === "price") {
    const field = (which: "min_price" | "max_price", label: string) => (
      <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-muted">
        {label}
        <span className="flex h-11 items-center gap-1 rounded-xl border-[1.5px] border-line bg-surface px-3 focus-within:border-primary">
          <span aria-hidden="true">$</span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={draft[which] ?? ""}
            onChange={(e) => setDraft({ ...draft, [which]: e.target.value === "" ? null : Number(e.target.value) })}
            className="h-full min-w-0 flex-1 border-0 bg-transparent text-base text-ink outline-none"
          />
        </span>
      </label>
    );
    body = (
      <div className="flex gap-2">
        {field("min_price", "Min")}
        {field("max_price", "Max")}
      </div>
    );
  } else if (k === "size") {
    body = (
      <div className="flex flex-col gap-3">
        <Group label="Letter">
          {SIZE_OPTIONS.letter.map((s) => (
            <ToggleChip key={s} size="sm" pressed={sizes.includes(s)} onClick={() => setSizes(s)}>
              {s}
            </ToggleChip>
          ))}
        </Group>
        <Group label="Numeric (tops, dresses)">
          {SIZE_OPTIONS.numeric.map((s) => (
            <ToggleChip key={s} size="sm" pressed={sizes.includes(s)} onClick={() => setSizes(s)}>
              {s}
            </ToggleChip>
          ))}
        </Group>
        <Group label="Waist (bottoms)">
          {SIZE_OPTIONS.waist.map((s) => (
            <ToggleChip key={s} size="sm" pressed={sizes.includes(s)} onClick={() => setSizes(s)}>
              {s}
            </ToggleChip>
          ))}
        </Group>
        <Group label="Shoes (US)">
          {SIZE_OPTIONS.shoes.map((s) => (
            <ToggleChip key={s} size="sm" pressed={sizes.includes(s)} onClick={() => setSizes(s)}>
              {s}
            </ToggleChip>
          ))}
        </Group>
      </div>
    );
  } else if (k === "condition") {
    body = (
      <div className="flex flex-wrap gap-1.5">
        {CONDITIONS.map((c) => (
          <ToggleChip
            key={c.key}
            pressed={draft.conditions.includes(c.key)}
            onClick={() => setDraft({ ...draft, conditions: toggle(draft.conditions, c.key) })}
          >
            {c.label}
          </ToggleChip>
        ))}
      </div>
    );
  } else if (k === "colour") {
    body = (
      <div className="flex flex-wrap gap-2">
        {COLOR_SWATCHES.map((c) => (
          <Swatch
            key={c.name}
            {...c}
            selected={draft.colors.includes(c.name)}
            onClick={() => setDraft({ ...draft, colors: toggle(draft.colors, c.name) })}
          />
        ))}
      </div>
    );
  } else if (k === "gender") {
    body = (
      <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Gender">
        {(
          [
            ["women", "Women's"],
            ["men", "Men's"],
            ["any", "Any"],
          ] as const
        ).map(([v, label]) => (
          <ToggleChip key={v} pressed={(draft.gender || "any") === v} onClick={() => setDraft({ ...draft, gender: v })}>
            {label}
          </ToggleChip>
        ))}
      </div>
    );
  } else if (k === "listed_within") {
    body = (
      <div className="flex flex-wrap gap-1.5">
        {WITHIN.map((w) => (
          <ToggleChip
            key={w.value}
            pressed={draft.within_days === w.value}
            onClick={() => setDraft({ ...draft, within_days: draft.within_days === w.value ? null : w.value })}
          >
            {w.label}
          </ToggleChip>
        ))}
        <ToggleChip pressed={draft.within_days == null} onClick={() => setDraft({ ...draft, within_days: null })}>
          Any time
        </ToggleChip>
      </div>
    );
  } else if (k === "location") {
    body = (
      <select
        id={id}
        disabled
        aria-describedby={`${id}-note`}
        className="h-11 w-full rounded-xl border-[1.5px] border-line-soft bg-bg px-3 text-[15px] text-muted"
      >
        <option>Any US state</option>
        {US_STATES.map((s) => (
          <option key={s}>{s}</option>
        ))}
      </select>
    );
  } else if (k === "store") {
    body = (
      <div className="flex flex-wrap gap-1.5">
        {LIVE_STORES.map((p) => (
          <ToggleChip key={p} pressed={draft.stores.includes(p)} onClick={() => setDraft({ ...draft, stores: toggle(draft.stores, p) })}>
            {STORE_LABELS[p]}
          </ToggleChip>
        ))}
        {SOON_STORES.map((p) => (
          <ToggleChip key={p} pressed={false} disabled onClick={() => undefined}>
            {STORE_LABELS[p]} · soon
          </ToggleChip>
        ))}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      {body}
      {note && (
        <p id={`${id}-note`} className="m-0 text-xs text-muted">
          {note}
        </p>
      )}
    </div>
  );
}

function clearOne(k: FilterKey, f: SearchFilters): SearchFilters {
  switch (k) {
    case "price":
      return { ...f, min_price: null, max_price: null };
    case "size":
      return { ...f, sizes: [] };
    case "condition":
      return { ...f, conditions: [] };
    case "colour":
      return { ...f, colors: [] };
    case "gender":
      return { ...f, gender: "any" };
    case "listed_within":
      return { ...f, within_days: null };
    case "store":
      return { ...f, stores: [] };
    default:
      return f;
  }
}

/**
 * Search filters (B4). Desktop: a row of dropdown chips, each with Apply.
 * Phone: a "Filters" button that opens a bottom sheet. Filters whose field
 * the stores don't send stay visible but disabled, with the reason.
 */
export function FilterBar({
  value,
  support = DEFAULT_SUPPORT,
  onApply,
  fromProfile = false,
}: {
  value: SearchFilters;
  support?: FilterSupport;
  onApply: (f: SearchFilters) => void;
  fromProfile?: boolean;
}) {
  const [open, setOpen] = useState<FilterKey | null>(null);
  const [sheet, setSheet] = useState(false);
  const [draft, setDraft] = useState<SearchFilters>(value);
  const rowRef = useRef<HTMLDivElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const count = activeCount(value);

  useEffect(() => setDraft(value), [value]);

  useEffect(() => {
    if (!open && !sheet) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(null);
        setSheet(false);
      }
    };
    const onClick = (e: MouseEvent) => {
      if (open && rowRef.current && !rowRef.current.contains(e.target as Node)) setOpen(null);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [open, sheet]);

  useEffect(() => {
    if (sheet) sheetRef.current?.focus();
  }, [sheet]);

  function apply(next: SearchFilters) {
    setOpen(null);
    setSheet(false);
    onApply(next);
  }

  return (
    <div className="min-w-0">
      {/* Phone: one button, then a bottom sheet */}
      <div className="flex items-center gap-2 md:hidden">
        <button
          type="button"
          onClick={() => {
            setDraft(value);
            setSheet(true);
          }}
          aria-haspopup="dialog"
          className="flex h-11 items-center gap-2 rounded-full border-[1.5px] border-ink bg-surface px-4 text-sm font-bold"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M4 6h16M7 12h10M10 18h4" strokeLinecap="round" />
          </svg>
          Filters
          {count > 0 && (
            <span className="rounded-full bg-primary px-1.5 text-xs text-white" aria-label={`${count} on`}>
              {count}
            </span>
          )}
        </button>
        {fromProfile && <span className="text-xs text-muted">Pre-filled from your profile</span>}
      </div>

      {/* Desktop: dropdown chips */}
      <div ref={rowRef} className="relative hidden flex-wrap items-center gap-1.5 md:flex" role="group" aria-label="Filters">
        {ORDER.map(({ key, label }) => {
          const available = support[key]?.available !== false;
          const shown = summary(key, value);
          const isOpen = open === key;
          return (
            <div key={key} className="relative">
              <button
                type="button"
                disabled={!available}
                aria-expanded={isOpen}
                aria-haspopup="dialog"
                title={!available ? support[key]?.note : undefined}
                onClick={() => {
                  setDraft(value);
                  setOpen(isOpen ? null : key);
                }}
                className={`flex h-10 items-center gap-1 rounded-full border-[1.5px] px-3 text-[13px] ${
                  shown ? "border-ink bg-ink font-bold text-white" : "border-line bg-surface text-ink hover:border-ink"
                } disabled:cursor-not-allowed disabled:border-dashed disabled:border-line disabled:bg-bg disabled:text-muted`}
              >
                {shown ? `${label}: ${shown}` : label}
                {!available ? <span className="sr-only">: {support[key]?.note}</span> : <span aria-hidden="true">▾</span>}
              </button>
              {isOpen && (
                <div
                  role="dialog"
                  aria-label={`${label} filter`}
                  className="absolute left-0 top-12 z-30 flex w-[340px] flex-col gap-3 rounded-2xl border border-line-blue bg-surface p-4 shadow-lg"
                >
                  <div className="text-sm font-bold">{label}</div>
                  <Section k={key} draft={draft} setDraft={setDraft} support={support} />
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => apply(clearOne(key, value))}
                      className="h-10 rounded-xl px-3 text-sm font-bold text-ink hover:bg-bg"
                    >
                      Clear
                    </button>
                    <button
                      type="button"
                      onClick={() => apply(draft)}
                      className="h-10 rounded-xl bg-primary px-4 text-sm font-bold text-white hover:bg-primary-hover"
                    >
                      Apply
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {!support.location.available && (
          <span className="text-xs text-muted">Location: {support.location.note}</span>
        )}
        {fromProfile && <span className="text-xs text-muted">· Pre-filled from your profile</span>}
      </div>

      {sheet && (
        <div className="fixed inset-0 z-50 flex items-end bg-ink/40 md:hidden" onClick={() => setSheet(false)}>
          <div
            ref={sheetRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="filters-title"
            tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
            className="flex max-h-[88dvh] w-full flex-col rounded-t-3xl bg-surface outline-none"
          >
            <div className="flex items-center justify-between border-b border-line-soft px-4 py-3">
              <h2 id="filters-title" className="m-0 font-heading text-lg font-bold">
                Filters
              </h2>
              <button
                type="button"
                onClick={() => setSheet(false)}
                aria-label="Close filters"
                className="flex h-11 w-11 items-center justify-center rounded-full text-xl hover:bg-bg"
              >
                ×
              </button>
            </div>
            <div className="flex flex-col gap-5 overflow-y-auto px-4 py-4">
              {ORDER.map(({ key, label }) => (
                <section key={key} className="flex flex-col gap-2" aria-label={label}>
                  <h3 className={`m-0 text-sm font-bold ${support[key]?.available === false ? "text-muted" : ""}`}>{label}</h3>
                  <Section k={key} draft={draft} setDraft={setDraft} support={support} />
                </section>
              ))}
            </div>
            <div className="flex gap-2 border-t border-line-soft p-4">
              <button
                type="button"
                onClick={() => setDraft({ ...EMPTY_FILTERS, sizes: [], gender: "any" })}
                className="h-12 flex-1 rounded-xl border-[1.5px] border-ink bg-surface font-bold"
              >
                Clear all
              </button>
              <button
                type="button"
                onClick={() => apply(draft)}
                className="h-12 flex-[2] rounded-xl bg-primary font-bold text-white hover:bg-primary-hover"
              >
                Show results
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
