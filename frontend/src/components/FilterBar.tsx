"use client";

import { useEffect, useId, useRef, useState } from "react";
import { activeCount, EMPTY_FILTERS } from "@/lib/filters";
import { COLOR_SWATCHES, CONDITIONS, money, SIZE_OPTIONS, STORE_LABELS } from "@/lib/format";
import type { FilterKey, FilterSupport, Platform, SearchFilters } from "@/lib/types";
import { SizeChip, SizeRow, Swatch, ToggleChip, toggle } from "./Chips";

const LIVE_STORES: Platform[] = ["ebay", "etsy", "depop", "poshmark", "mercari"];
const SOON_STORES: Platform[] = ["fb_marketplace"];
const DEFAULT_LOCATION = "New York, NY";
const WITHIN = [
  { value: 1, label: "24 h" },
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
] as const;

// Used when the API hasn't said yet (Home, before any search). Same as backend FILTER_SUPPORT.
export const DEFAULT_SUPPORT: FilterSupport = {
  price: { available: true },
  size: { available: true, note: "eBay and Etsy listings don't state a size; they stay in, after the matches." },
  condition: { available: true, note: "Matched on the condition each store states." },
  colour: { available: true, note: "Matched on colours named in the listing title." },
  gender: { available: true, note: "Matched on Men's / Women's in the title." },
  listed_within: { available: true, note: "Only Poshmark shares listing dates; other stores' items are hidden while this is on." },
  location: { available: false, note: "Location is for Facebook Marketplace, which isn't connected yet." },
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
    case "location":
      return f.location;
    default:
      return null;
  }
}

function SizeGroup({ label, options, value, onToggle }: {
  label: string;
  options: string[];
  value: string[];
  onToggle: (v: string) => void;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="text-xs font-bold text-muted">{label}</div>
      <SizeRow count={options.length}>
        {options.map((s) => (
          <SizeChip key={s} pressed={value.includes(s)} onClick={() => onToggle(s)}>
            {s}
          </SizeChip>
        ))}
      </SizeRow>
    </div>
  );
}

const FILTER_SIZES = {
  letter: [...SIZE_OPTIONS.letter, ...SIZE_OPTIONS.plusLetter],
  numeric: SIZE_OPTIONS.numeric,
  waist: [...SIZE_OPTIONS.waist, ...SIZE_OPTIONS.menWaist.filter((w) => Number(w) > 34)],
  shoes: [...new Set([...SIZE_OPTIONS.shoes, ...SIZE_OPTIONS.menShoes])].sort((a, b) => Number(a) - Number(b)),
};

/** Number input that reports a value once typing pauses, so each keystroke isn't a search. */
function PriceField({ label, value, onCommit }: { label: string; value: number | null; onCommit: (v: number | null) => void }) {
  const [text, setText] = useState(value == null ? "" : String(value));
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => setText(value == null ? "" : String(value)), [value]);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-muted">
      {label}
      <span className="flex h-11 items-center gap-1 rounded-xl border-[1.5px] border-line bg-surface px-3 focus-within:border-primary">
        <span aria-hidden="true">$</span>
        <input
          type="number"
          inputMode="decimal"
          min={0}
          value={text}
          onChange={(e) => {
            const next = e.target.value;
            setText(next);
            if (timer.current) clearTimeout(timer.current);
            timer.current = setTimeout(() => {
              const n = Number(next);
              if (next === "") onCommit(null);
              else if (Number.isFinite(n) && n >= 0) onCommit(n);
            }, 600);
          }}
          className="h-full min-w-0 flex-1 border-0 bg-transparent text-base text-ink outline-none"
        />
      </span>
    </label>
  );
}

/** The editor for one filter, used in both the desktop popover and the phone sheet. Every change applies at once. */
function Section({
  k,
  value: draft,
  onChange: setDraft,
  support,
}: {
  k: FilterKey;
  value: SearchFilters;
  onChange: (f: SearchFilters) => void;
  support: FilterSupport;
}) {
  const id = useId();
  const note = support[k]?.note;
  const sizes = draft.sizes || [];
  const setSizes = (v: string) => setDraft({ ...draft, sizes: toggle(sizes, v) });
  let body: React.ReactNode = null;

  if (k === "price") {
    body = (
      <div className="flex gap-2">
        <PriceField label="Min" value={draft.min_price} onCommit={(v) => setDraft({ ...draft, min_price: v })} />
        <PriceField label="Max" value={draft.max_price} onCommit={(v) => setDraft({ ...draft, max_price: v })} />
      </div>
    );
  } else if (k === "size") {
    body = (
      <div className="flex flex-col gap-3">
        <SizeGroup label="Letter" options={FILTER_SIZES.letter} value={sizes} onToggle={setSizes} />
        <SizeGroup label="Numeric (tops, dresses)" options={FILTER_SIZES.numeric} value={sizes} onToggle={setSizes} />
        <SizeGroup label="Waist (bottoms)" options={FILTER_SIZES.waist} value={sizes} onToggle={setSizes} />
        <SizeGroup label="Shoes (US)" options={FILTER_SIZES.shoes} value={sizes} onToggle={setSizes} />
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
    const enabled = support.location?.available !== false;
    body = (
      <label className="flex flex-col gap-1 text-xs text-muted">
        US ZIP or city · FB Marketplace only
        <input
          id={id}
          disabled={!enabled}
          aria-describedby={`${id}-note`}
          defaultValue={draft.location || DEFAULT_LOCATION}
          maxLength={80}
          onBlur={(e) => enabled && setDraft({ ...draft, location: e.target.value.trim() || null })}
          className="h-11 w-full rounded-xl border-[1.5px] border-line bg-surface px-3 text-base text-ink outline-none focus:border-primary disabled:border-line-soft disabled:bg-bg disabled:text-muted"
        />
      </label>
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
            {STORE_LABELS[p]} · coming soon
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
    case "location":
      return { ...f, location: null };
    default:
      return f;
  }
}

/**
 * Search filters (B4). Every choice applies at once: the results page updates
 * the URL and searches again without a model call. Desktop: a row of dropdown
 * chips. Phone: a "Filters" button that opens a bottom sheet whose button
 * shows the live result count. Filters whose field the stores don't send
 * stay visible but disabled, with the reason.
 */
export function FilterBar({
  value,
  support = DEFAULT_SUPPORT,
  onChange,
  fromProfile = false,
  resultCount = null,
  busy = false,
}: {
  value: SearchFilters;
  support?: FilterSupport;
  onChange: (f: SearchFilters) => void;
  fromProfile?: boolean;
  /** Results for the current filters (null before the first search). */
  resultCount?: number | null;
  busy?: boolean;
}) {
  const [open, setOpen] = useState<FilterKey | null>(null);
  const [sheet, setSheet] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const count = activeCount(value);

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

  const showLabel = busy || resultCount == null ? "Show results" : `Show ${resultCount} result${resultCount === 1 ? "" : "s"}`;

  return (
    <div className="min-w-0">
      {/* Phone: one button, then a bottom sheet */}
      <div className="flex items-center gap-2 md:hidden">
        <button
          type="button"
          onClick={() => setSheet(true)}
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
          const shown = available ? summary(key, value) : null;
          const isOpen = open === key;
          return (
            <div key={key} className="relative">
              <button
                type="button"
                disabled={!available}
                aria-expanded={isOpen}
                aria-haspopup="dialog"
                title={!available ? support[key]?.note : undefined}
                onClick={() => setOpen(isOpen ? null : key)}
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
                  className="absolute left-0 top-12 z-30 flex w-[360px] flex-col gap-3 rounded-2xl border border-line-blue bg-surface p-4 shadow-lg"
                >
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-bold">{label}</div>
                    <div className="text-xs text-muted" aria-live="polite">
                      {busy ? "Updating…" : resultCount != null ? `${resultCount} result${resultCount === 1 ? "" : "s"}` : ""}
                    </div>
                  </div>
                  <Section k={key} value={value} onChange={onChange} support={support} />
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => onChange(clearOne(key, value))}
                      className="h-10 rounded-xl px-3 text-sm font-bold text-ink hover:bg-bg"
                    >
                      Clear
                    </button>
                    <button
                      type="button"
                      onClick={() => setOpen(null)}
                      className="h-10 rounded-xl bg-primary px-4 text-sm font-bold text-white hover:bg-primary-hover"
                    >
                      Done
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {fromProfile && <span className="text-xs text-muted">Pre-filled from your profile</span>}
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
                <section key={key} className="flex min-w-0 flex-col gap-2" aria-label={label}>
                  <h3 className={`m-0 text-sm font-bold ${support[key]?.available === false ? "text-muted" : ""}`}>{label}</h3>
                  <Section k={key} value={value} onChange={onChange} support={support} />
                </section>
              ))}
            </div>
            <div className="flex gap-2 border-t border-line-soft p-4">
              <button
                type="button"
                onClick={() => onChange({ ...EMPTY_FILTERS, sizes: [], gender: "any" })}
                className="h-12 flex-1 rounded-xl border-[1.5px] border-ink bg-surface font-bold"
              >
                Clear all
              </button>
              <button
                type="button"
                onClick={() => setSheet(false)}
                aria-live="polite"
                className="h-12 flex-[2] rounded-xl bg-primary font-bold text-white hover:bg-primary-hover"
              >
                {showLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
