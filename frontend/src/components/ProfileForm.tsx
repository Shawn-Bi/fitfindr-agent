"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { COLOR_SWATCHES, STYLES } from "@/lib/format";
import type { Profile, Sizes } from "@/lib/types";
import { FormMessage, PrimaryButton } from "./AuthForm";

const TOP_SIZES = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL"];
const WAISTS = Array.from({ length: 21 }, (_, i) => String(24 + i));
const LENGTHS = Array.from({ length: 11 }, (_, i) => String(26 + i));
const SHOES = Array.from({ length: 21 }, (_, i) => String(5 + i / 2));
const PROFILE_COLORS = COLOR_SWATCHES.filter((c) =>
  ["black", "white", "denim blue", "rust", "olive", "pink", "cream", "grey"].includes(c.name),
);

function Select({ label, value, options, onChange }: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-[46px] rounded-[10px] border-[1.5px] border-line bg-surface px-2 text-[15px] text-ink"
      >
        <option value="">Not set</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ToggleChip({ pressed, onClick, children }: { pressed: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={`h-11 rounded-full border-[1.5px] px-3.5 text-sm ${
        pressed ? "border-ink bg-ink font-bold text-white" : "border-line bg-surface text-ink hover:border-ink"
      }`}
    >
      {children}
    </button>
  );
}

export function Swatch({ name, hex, selected, onClick }: { name: string; hex: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      aria-label={name}
      title={name}
      style={{ background: hex }}
      className={`h-11 w-11 shrink-0 rounded-full ${
        selected ? "border-[3px] border-white shadow-[0_0_0_2px_#0369A1]" : "border-[1.5px] border-line"
      }`}
    />
  );
}

function toggle(list: string[], value: string) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/** Sizes, styles, colors and budget — every field optional (P3, Profile). */
export function ProfileForm({ initial, submitLabel, onSaved }: {
  initial: Profile | null;
  submitLabel: string;
  onSaved: (p: Profile) => void;
}) {
  const [sizes, setSizes] = useState<Sizes>(initial?.sizes || {});
  const [styles, setStyles] = useState<string[]>(initial?.styles || []);
  const [colors, setColors] = useState<string[]>(initial?.colors || []);
  const [budget, setBudget] = useState(initial?.budget != null ? String(initial.budget) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const amount = budget.trim() === "" ? null : Number(budget);
    if (amount !== null && (!Number.isFinite(amount) || amount < 0)) {
      return setError("Budget must be a dollar amount, like 40.");
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await api<Profile>("/profile", {
        method: "PATCH",
        json: { sizes, styles, colors, budget: amount },
      });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const set = (key: keyof Sizes) => (v: string) => setSizes({ ...sizes, [key]: v || undefined });

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      {error && <FormMessage>{error}</FormMessage>}
      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-1 p-0 text-sm font-bold">Usual sizes (US)</legend>
        <p className="m-0 text-[13px] text-muted">Filters results to your size. You can remove it on any search.</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Select label="Tops" value={sizes.top || ""} options={TOP_SIZES} onChange={set("top")} />
          <Select label="Waist" value={sizes.waist || ""} options={WAISTS} onChange={set("waist")} />
          <Select label="Length" value={sizes.length || ""} options={LENGTHS} onChange={set("length")} />
          <Select label="Shoes (US)" value={sizes.shoe || ""} options={SHOES} onChange={set("shoe")} />
        </div>
      </fieldset>

      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-1 p-0 text-sm font-bold">Styles you like</legend>
        <p className="mb-2 mt-0 text-[13px] text-muted">Ranks finds that match your taste higher.</p>
        <div className="flex flex-wrap gap-2">
          {STYLES.map((s) => (
            <ToggleChip key={s} pressed={styles.includes(s)} onClick={() => setStyles(toggle(styles, s))}>
              {s}
            </ToggleChip>
          ))}
        </div>
      </fieldset>

      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-1 p-0 text-sm font-bold">Colors you wear most</legend>
        <p className="mb-2 mt-0 text-[13px] text-muted">Helps pick pieces that go with what you own.</p>
        <div className="flex flex-wrap gap-2.5">
          {PROFILE_COLORS.map((c) => (
            <Swatch key={c.name} {...c} selected={colors.includes(c.name)} onClick={() => setColors(toggle(colors, c.name))} />
          ))}
        </div>
      </fieldset>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="budget" className="text-sm font-bold">
          Usual budget per item
        </label>
        <p className="m-0 text-[13px] text-muted">Used as a price limit when your search doesn&apos;t name one.</p>
        <div className="flex h-12 items-center gap-1.5 rounded-xl border-[1.5px] border-line bg-surface px-3.5 focus-within:border-primary">
          <span className="text-muted">up to $</span>
          <input
            id="budget"
            type="number"
            inputMode="decimal"
            min={0}
            step="1"
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            className="h-full min-w-0 flex-1 border-0 bg-transparent text-base outline-none"
          />
        </div>
      </div>

      <PrimaryButton type="submit" busy={busy}>
        {submitLabel}
      </PrimaryButton>
    </form>
  );
}
