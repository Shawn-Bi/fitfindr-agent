"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { COLOR_SWATCHES, PROFILE_STYLES, SIZE_OPTIONS } from "@/lib/format";
import type { Fit, Gender, Measurements, Profile, Sizes } from "@/lib/types";
import { FormMessage, PrimaryButton } from "./AuthForm";
import { Swatch, ToggleChip, toggle } from "./Chips";

// Re-exported for older imports.
export { Swatch, ToggleChip } from "./Chips";

const EMPTY_SIZES: Sizes = { tops: [], bottoms_waist: [], bottoms_inseam: [], bottoms: [], dresses: [], shoes: [] };
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

function SizeGroup({ label, options, value, onChange }: {
  label: string;
  options: string[];
  value: string[];
  onChange: (v: string[]) => void;
}) {
  return (
    <fieldset className="m-0 min-w-0 border-0 p-0">
      <legend className="mb-1.5 p-0 text-xs font-bold text-muted">{label}</legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => (
          <ToggleChip key={o} size="sm" pressed={value.includes(o)} onClick={() => onChange(toggle(value, o))}>
            {o}
          </ToggleChip>
        ))}
      </div>
    </fieldset>
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
          sizes: gender === "men" ? { ...sizes, dresses: [] } : sizes,
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

  const setSize = (key: keyof Sizes) => (v: string[]) => setSizes({ ...sizes, [key]: v });

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

      <Card id="pf-sizes" title="Your sizes (US)" hint="Pick every size you wear. Searches use the ones that fit what you're looking for; you can remove them on any search.">
        <div className="grid gap-5 md:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-3">
            <h3 className="m-0 text-sm font-bold">Tops</h3>
            <SizeGroup label="Letter" options={SIZE_OPTIONS.letter} value={sizes.tops} onChange={setSize("tops")} />
            <SizeGroup label="Numeric" options={SIZE_OPTIONS.numeric} value={sizes.tops} onChange={setSize("tops")} />
          </div>
          <div className="flex min-w-0 flex-col gap-3">
            <h3 className="m-0 text-sm font-bold">Bottoms</h3>
            <SizeGroup label="Waist (in)" options={SIZE_OPTIONS.waist} value={sizes.bottoms_waist} onChange={setSize("bottoms_waist")} />
            <SizeGroup label="Inseam (in)" options={SIZE_OPTIONS.inseam} value={sizes.bottoms_inseam} onChange={setSize("bottoms_inseam")} />
            <SizeGroup label="Letter" options={SIZE_OPTIONS.bottomsLetter} value={sizes.bottoms} onChange={setSize("bottoms")} />
          </div>
          {gender !== "men" && (
            <div className="flex min-w-0 flex-col gap-3">
              <h3 className="m-0 text-sm font-bold">Dresses</h3>
              <SizeGroup label="Numeric and letter" options={SIZE_OPTIONS.dresses} value={sizes.dresses} onChange={setSize("dresses")} />
            </div>
          )}
          <div className="flex min-w-0 flex-col gap-3">
            <h3 className="m-0 text-sm font-bold">Shoes</h3>
            <SizeGroup label="US size" options={SIZE_OPTIONS.shoes} value={sizes.shoes} onChange={setSize("shoes")} />
          </div>
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
