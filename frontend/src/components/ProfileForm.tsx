"use client";

import Link from "next/link";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { COLOR_SWATCHES, INSEAM_HINT, PROFILE_STYLES, SIZE_OPTIONS } from "@/lib/format";
import type { Fit, Gender, Measurements, Profile, SizeRange, Sizes } from "@/lib/types";
import { FormMessage, PrimaryButton } from "./AuthForm";
import { SizeChip, SizeRow, Swatch, ToggleChip, toggle } from "./Chips";

// Re-exported for older imports.
export { Swatch, ToggleChip } from "./Chips";

const EMPTY_SIZES: Sizes = {
  size_range: [], tops: [], bottoms_waist: [], bottoms_inseam: [], shoes: [],
  men_tops: [], men_neck: [], men_sleeve: [], men_waist: [], men_inseam: [], men_shoes: [],
};
const RANGES: { key: SizeRange; label: string }[] = [
  { key: "regular", label: "Regular" },
  { key: "petite", label: "Petite" },
  { key: "plus", label: "Plus" },
];
export const DEFAULT_LOCATION = "New York, NY";
const FITS: { key: Fit; label: string; hint: string }[] = [
  { key: "slim", label: "Slim", hint: "Close to the body" },
  { key: "regular", label: "Regular", hint: "True to size" },
  { key: "relaxed", label: "Relaxed", hint: "A little room" },
  { key: "oversized", label: "Oversized", hint: "Roomy and boxy" },
];
const MEASURES = ["bust", "waist", "hips", "height"] as const;

function Card({ title, hint, children, id }: { title: string; hint?: string; children: React.ReactNode; id: string }) {
  return (
    <section aria-labelledby={id} className="flex min-w-0 flex-col gap-3 rounded-[18px] border border-line-blue bg-surface p-4 md:p-5">
      <div>
        <h2 id={id} className="m-0 font-heading text-[17px] font-bold">
          {title}
        </h2>
        {hint && <p className="m-0 mt-0.5 text-[13px] text-muted">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function Row({ label, options, value, onChange, hint }: {
  label?: string;
  options: string[];
  value: string[];
  onChange: (v: string[]) => void;
  hint?: (o: string) => string | undefined;
}) {
  return (
    <fieldset className="m-0 min-w-0 border-0 p-0">
      {label && <legend className="mb-1.5 p-0 text-xs font-bold text-muted">{label}</legend>}
      <SizeRow count={options.length}>
        {options.map((o) => (
          <SizeChip key={o} pressed={value.includes(o)} onClick={() => onChange(toggle(value, o))} label={hint?.(o) ? `${o} (${hint(o)})` : undefined}>
            {o}
          </SizeChip>
        ))}
      </SizeRow>
    </fieldset>
  );
}

/** One collapsible size group: open while nothing is picked, otherwise closed showing the picks. */
function SizeGroup({ title, picked, children }: { title: string; picked: string[]; children: React.ReactNode }) {
  const [startOpen] = useState(picked.length === 0); // decided once, so picking a size doesn't fold the group
  return (
    <details open={startOpen} className="group min-w-0 rounded-xl border border-line-soft bg-surface">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 [&::-webkit-details-marker]:hidden">
        <span className="shrink-0 text-sm font-bold">{title}</span>
        <span className="flex min-w-0 items-center gap-2 text-[13px] text-muted">
          <span className="truncate">{picked.length ? picked.join(", ") : "Not set"}</span>
          <span aria-hidden="true" className="transition-transform group-open:rotate-180">▾</span>
        </span>
      </summary>
      <div className="flex flex-col gap-3 px-3 pb-3">{children}</div>
    </details>
  );
}

function convert(m: Measurements, to: "in" | "cm"): Measurements {
  const from = m.unit || "in";
  if (from === to) return m;
  const factor = to === "cm" ? 2.54 : 1 / 2.54;
  const out: Measurements = { unit: to };
  for (const k of MEASURES) {
    const v = m[k];
    if (v != null) out[k] = Math.round(v * factor * 10) / 10;
  }
  return out;
}

function topsFor(range: SizeRange): string[] {
  return range === "plus" ? [...SIZE_OPTIONS.plusLetter, ...SIZE_OPTIONS.plusNumeric] : [...SIZE_OPTIONS.letter, ...SIZE_OPTIONS.numeric];
}

/** Only the groups "Shopping for" shows are saved, and tops only from the chosen size range. */
function sizesToSave(sizes: Sizes, gender: Gender | null): Sizes {
  const range = sizes.size_range[0] || "regular";
  const tops = topsFor(range);
  const women = gender !== "men";
  const men = gender !== "women";
  return {
    size_range: women ? [range] : [],
    tops: women ? sizes.tops.filter((t) => tops.includes(t)) : [],
    bottoms_waist: women ? sizes.bottoms_waist : [],
    bottoms_inseam: women ? sizes.bottoms_inseam.filter((i) => SIZE_OPTIONS.inseam.includes(i)) : [],
    shoes: women ? sizes.shoes : [],
    men_tops: men ? sizes.men_tops : [],
    men_neck: men ? sizes.men_neck : [],
    men_sleeve: men ? sizes.men_sleeve : [],
    men_waist: men ? sizes.men_waist : [],
    men_inseam: men ? sizes.men_inseam : [],
    men_shoes: men ? sizes.men_shoes : [],
  };
}

/**
 * The profile (P3 and Profile, B3): who you shop for, sizes per category,
 * optional measurements, fit, styles, colours and a budget range. Every
 * field is optional; search, ranking and the stylist all use them.
 */
export function ProfileForm({ initial, submitLabel, onSaved }: {
  initial: Profile | null;
  submitLabel: string;
  onSaved: (p: Profile) => void;
}) {
  const [gender, setGender] = useState<Gender | null>(initial?.gender ?? null);
  const [sizes, setSizes] = useState<Sizes>({ ...EMPTY_SIZES, ...(initial?.sizes || {}) });
  const [measurements, setMeasurements] = useState<Measurements>({ unit: "in", ...(initial?.measurements || {}) });
  const [fit, setFit] = useState<Fit | null>(initial?.fit ?? null);
  const [styles, setStyles] = useState<string[]>(initial?.styles || []);
  const [colors, setColors] = useState<string[]>(initial?.colors || []);
  const [budgetMin, setBudgetMin] = useState(initial?.budget_min != null ? String(initial.budget_min) : "");
  const [budgetMax, setBudgetMax] = useState(initial?.budget != null ? String(initial.budget) : "");
  const [location, setLocation] = useState(initial?.location || DEFAULT_LOCATION);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const unit = measurements.unit || "in";
  const chestLabel = gender === "men" ? "Chest" : gender === "women" ? "Bust" : "Bust / chest";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const low = budgetMin.trim() === "" ? null : Number(budgetMin);
    const high = budgetMax.trim() === "" ? null : Number(budgetMax);
    for (const v of [low, high]) {
      if (v !== null && (!Number.isFinite(v) || v < 0)) return setError("Budget must be dollar amounts, like 10 and 40.");
    }
    if (low !== null && high !== null && low > high) return setError("The lowest price can't be above the highest.");
    setBusy(true);
    setError(null);
    try {
      const saved = await api<Profile>("/profile", {
        method: "PATCH",
        json: {
          gender,
          sizes: sizesToSave(sizes, gender),
          location: location.trim() || null,
          measurements,
          fit,
          styles,
          colors,
          budget_min: low,
          budget: high,
        },
      });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const setSize = (key: Exclude<keyof Sizes, "size_range">) => (v: string[]) => setSizes({ ...sizes, [key]: v });
  const range: SizeRange = sizes.size_range[0] || "regular";
  const plus = range === "plus";
  const topOptions = topsFor(range);
  const pickedTops = sizes.tops.filter((t) => topOptions.includes(t));
  const showWomen = gender !== "men";
  const showMen = gender !== "women";

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      {error && <FormMessage>{error}</FormMessage>}

      <div className="grid gap-4 md:grid-cols-2">
        <Card id="pf-gender" title="Shopping for" hint="Filters out pieces cut for someone else. Kids' items are always hidden.">
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-labelledby="pf-gender">
            {(
              [
                ["women", "Women"],
                ["men", "Men"],
                ["both", "Both"],
              ] as const
            ).map(([v, label]) => (
              <ToggleChip key={v} pressed={gender === v} onClick={() => setGender(gender === v ? null : v)}>
                {label}
              </ToggleChip>
            ))}
          </div>
        </Card>

        <Card id="pf-fit" title="Fit preference" hint="How you like clothes to sit. Used in ranking and styling.">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {FITS.map((f) => (
              <button
                key={f.key}
                type="button"
                aria-pressed={fit === f.key}
                onClick={() => setFit(fit === f.key ? null : f.key)}
                className={`flex min-h-[56px] flex-col items-start justify-center rounded-xl border-[1.5px] px-3 py-2 text-left ${
                  fit === f.key ? "border-ink bg-ink text-white" : "border-line bg-surface text-ink hover:border-ink"
                }`}
              >
                <span className="text-sm font-bold">{f.label}</span>
                <span className={`text-[11px] ${fit === f.key ? "text-white" : "text-muted"}`}>{f.hint}</span>
              </button>
            ))}
          </div>
        </Card>
      </div>

      <Card id="pf-sizes" title="Your sizes (US)" hint="Pick every size you wear. Searches show these sizes first and never hide a listing for its size.">
        <Link href="/size-guide" className="-mt-2 inline-flex min-h-11 items-center self-start text-sm font-bold">
          Size guide
        </Link>
        <div className={`grid gap-4 ${showWomen && showMen ? "md:grid-cols-2" : ""}`}>
          {showWomen && (
            <div className="flex min-w-0 flex-col gap-2.5">
              {showMen && <h3 className="m-0 text-sm font-bold">Women</h3>}
              <div role="radiogroup" aria-label="Size range" className="flex rounded-xl bg-bg p-1">
                {RANGES.map((r) => (
                  <button
                    key={r.key}
                    type="button"
                    role="radio"
                    aria-checked={range === r.key}
                    onClick={() => setSizes({ ...sizes, size_range: [r.key] })}
                    className={`h-11 flex-1 rounded-lg text-sm ${range === r.key ? "bg-primary font-bold text-white" : "text-ink hover:bg-tint"}`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
              <div className={`grid gap-2.5 ${showMen ? "" : "md:grid-cols-2"}`}>
                <SizeGroup title="Tops & dresses" picked={pickedTops}>
                  <Row label="Letter" options={plus ? SIZE_OPTIONS.plusLetter : SIZE_OPTIONS.letter} value={sizes.tops} onChange={setSize("tops")} />
                  <Row label="Numeric" options={plus ? SIZE_OPTIONS.plusNumeric : SIZE_OPTIONS.numeric} value={sizes.tops} onChange={setSize("tops")} />
                </SizeGroup>
                <SizeGroup title="Jeans · waist" picked={sizes.bottoms_waist}>
                  <Row options={SIZE_OPTIONS.waist} value={sizes.bottoms_waist} onChange={setSize("bottoms_waist")} />
                </SizeGroup>
                <SizeGroup title="Pants · inseam" picked={sizes.bottoms_inseam}>
                  <Row options={SIZE_OPTIONS.inseam} value={sizes.bottoms_inseam} onChange={setSize("bottoms_inseam")} hint={(o) => INSEAM_HINT[o]} />
                  <p className="m-0 text-xs text-muted">Short 28–29 in · Regular 30–32 in · Long 33–34 in</p>
                </SizeGroup>
                <SizeGroup title="Shoes · US women's" picked={sizes.shoes}>
                  <Row options={SIZE_OPTIONS.shoes} value={sizes.shoes} onChange={setSize("shoes")} />
                </SizeGroup>
              </div>
            </div>
          )}
          {showMen && (
            <div className="flex min-w-0 flex-col gap-2.5">
              {showWomen && <h3 className="m-0 text-sm font-bold">Men</h3>}
              <div className={`grid gap-2.5 ${showWomen ? "" : "md:grid-cols-2"}`}>
                <SizeGroup title="Tops" picked={sizes.men_tops}>
                  <Row options={SIZE_OPTIONS.menTops} value={sizes.men_tops} onChange={setSize("men_tops")} />
                </SizeGroup>
                <SizeGroup title="Dress shirts" picked={[...sizes.men_neck.map((n) => `neck ${n}`), ...sizes.men_sleeve.map((n) => `sleeve ${n}`)]}>
                  <Row label="Neck (in)" options={SIZE_OPTIONS.menNeck} value={sizes.men_neck} onChange={setSize("men_neck")} />
                  <Row label="Sleeve (in)" options={SIZE_OPTIONS.menSleeve} value={sizes.men_sleeve} onChange={setSize("men_sleeve")} />
                </SizeGroup>
                <SizeGroup title="Pants" picked={[...sizes.men_waist.map((n) => `W${n}`), ...sizes.men_inseam.map((n) => `L${n}`)]}>
                  <Row label="Waist (in)" options={SIZE_OPTIONS.menWaist} value={sizes.men_waist} onChange={setSize("men_waist")} />
                  <Row label="Inseam (in)" options={SIZE_OPTIONS.menInseam} value={sizes.men_inseam} onChange={setSize("men_inseam")} />
                </SizeGroup>
                <SizeGroup title="Shoes · US men's" picked={sizes.men_shoes}>
                  <Row options={SIZE_OPTIONS.menShoes} value={sizes.men_shoes} onChange={setSize("men_shoes")} />
                </SizeGroup>
              </div>
            </div>
          )}
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card id="pf-measure" title="Body measurements (optional)" hint="Helps the stylist balance proportions. Only you can see them.">
          <div className="flex gap-1.5" role="radiogroup" aria-label="Units">
            {(["in", "cm"] as const).map((u) => (
              <ToggleChip key={u} size="sm" pressed={unit === u} onClick={() => setMeasurements(convert(measurements, u))}>
                {u === "in" ? "Inches" : "Centimeters"}
              </ToggleChip>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2">
            {MEASURES.map((k) => (
              <label key={k} className="flex min-w-0 flex-col gap-1 text-xs text-muted">
                {k === "bust" ? chestLabel : k === "waist" ? "Waist" : k === "hips" ? "Hips" : "Height"}
                <span className="flex h-12 items-center gap-1 rounded-xl border-[1.5px] border-line bg-surface px-3 focus-within:border-primary">
                  <input
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="0.5"
                    value={measurements[k] ?? ""}
                    onChange={(e) =>
                      setMeasurements({ ...measurements, [k]: e.target.value === "" ? undefined : Number(e.target.value) })
                    }
                    className="h-full min-w-0 flex-1 border-0 bg-transparent text-base text-ink outline-none"
                  />
                  <span aria-hidden="true">{unit}</span>
                </span>
              </label>
            ))}
          </div>
          <details className="rounded-xl bg-bg px-3 py-2 text-[13px]">
            <summary className="flex min-h-11 cursor-pointer items-center font-bold">How to measure</summary>
            <ul className="mb-1 mt-1 flex flex-col gap-1 pl-4 text-muted">
              <li>Use a soft tape, snug but not tight, over light clothing.</li>
              <li>{chestLabel}: around the fullest part, tape level under the arms.</li>
              <li>Waist: around your natural waist, the narrowest part above the belly button.</li>
              <li>Hips: around the fullest part of the hips and seat, feet together.</li>
              <li>Height: barefoot, back against a wall.</li>
            </ul>
          </details>
        </Card>

        <Card id="pf-budget" title="Budget per item" hint="Used as the price range when your search doesn't name one.">
          <div className="flex items-end gap-2">
            {(
              [
                ["Min", budgetMin, setBudgetMin, "budget-min"],
                ["Max", budgetMax, setBudgetMax, "budget-max"],
              ] as const
            ).map(([label, value, set, id]) => (
              <label key={id} htmlFor={id} className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-muted">
                {label}
                <span className="flex h-12 items-center gap-1 rounded-xl border-[1.5px] border-line bg-surface px-3 focus-within:border-primary">
                  <span aria-hidden="true">$</span>
                  <input
                    id={id}
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="1"
                    value={value}
                    onChange={(e) => set(e.target.value)}
                    className="h-full min-w-0 flex-1 border-0 bg-transparent text-base text-ink outline-none"
                  />
                </span>
              </label>
            ))}
          </div>
        </Card>
      </div>

      <Card id="pf-location" title="Your area" hint="A US ZIP code or city, for local-pickup listings on Facebook Marketplace (connecting soon).">
        <label htmlFor="pf-location-input" className="flex flex-col gap-1 text-xs text-muted">
          ZIP or city
          <input
            id="pf-location-input"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            maxLength={80}
            placeholder={DEFAULT_LOCATION}
            className="h-12 rounded-xl border-[1.5px] border-line bg-surface px-3 text-base text-ink outline-none focus:border-primary"
          />
        </label>
      </Card>

      <Card id="pf-styles" title="Styles you like" hint="Pick as many as you like. The stylist builds outfits in these; with none, it uses an elevated quiet-luxury look.">
        <div className="flex flex-wrap gap-2">
          {PROFILE_STYLES.map((s) => (
            <ToggleChip key={s} pressed={styles.includes(s)} onClick={() => setStyles(toggle(styles, s))}>
              {s}
            </ToggleChip>
          ))}
        </div>
      </Card>

      <Card id="pf-colors" title="Colours you wear most" hint="Finds in these colours rank a little higher.">
        <div className="flex flex-wrap gap-2.5 md:flex-nowrap md:justify-between md:gap-1">
          {COLOR_SWATCHES.map((c) => (
            <Swatch key={c.name} {...c} selected={colors.includes(c.name)} onClick={() => setColors(toggle(colors, c.name))} />
          ))}
        </div>
        <div className="text-xs text-muted" aria-live="polite">
          {colors.length ? `Selected: ${colors.join(", ")}` : "None selected"}
        </div>
      </Card>

      <PrimaryButton type="submit" busy={busy}>
        {submitLabel}
      </PrimaryButton>
    </form>
  );
}
