"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { shortDate } from "@/lib/format";
import type { StoreStatus } from "@/lib/types";

function note(s: StoreStatus): string | null {
  if (s.status === "paused") return s.resumes ? `paused until ${shortDate(s.resumes)}` : "paused";
  if (s.status === "coming_soon") return "coming soon";
  if (s.status === "error") return "unavailable";
  return null;
}

/** "Searching eBay · Etsy · …" with Paused / Coming soon flags (P1, P4). */
export function StoreBar({ className = "" }: { className?: string }) {
  const [stores, setStores] = useState<StoreStatus[] | null>(null);
  useEffect(() => {
    api<{ stores: StoreStatus[] }>("/stores")
      .then((d) => setStores(d.stores))
      .catch(() => setStores(null));
  }, []);

  if (!stores) {
    return (
      <p className={`m-0 text-xs leading-normal text-muted ${className}`}>
        Searching eBay · Etsy · Depop · Poshmark · Mercari · FB Marketplace
      </p>
    );
  }
  const live = stores.filter((s) => s.status === "live").length;
  return (
    <p className={`m-0 text-xs leading-normal text-muted ${className}`}>
      <span className="font-bold text-ink">{live} stores live:</span>{" "}
      {stores.map((s, i) => {
        const n = note(s);
        return (
          <span key={s.platform}>
            {i > 0 && " · "}
            {s.label}
            {n && <span className="text-muted"> ({n})</span>}
          </span>
        );
      })}
    </p>
  );
}

/** Store chips on the results page, with counts and paused dates. */
export function StorePanel({ stores, variant = "chips", hidden, onToggle }: {
  stores: StoreStatus[];
  variant?: "chips" | "filters";
  hidden?: Set<string>;
  onToggle?: (platform: string) => void;
}) {
  const live = stores.filter((s) => s.status === "live").length;
  if (variant === "filters") {
    return (
      <fieldset className="m-0 flex flex-col gap-1 rounded-2xl border-0 bg-tint p-4">
        <legend className="float-left mb-2 p-0 text-[15px] font-bold">Stores · {live} live</legend>
        {stores.map((s) => {
          const usable = s.status === "live";
          const n = note(s);
          return (
            <label key={s.platform} className={`flex min-h-11 items-center gap-2.5 text-sm ${usable ? "" : "text-muted"}`}>
              <input
                type="checkbox"
                className="h-5 w-5 accent-primary"
                checked={usable && !hidden?.has(s.platform)}
                disabled={!usable}
                onChange={() => onToggle?.(s.platform)}
              />
              {s.label}
              <span className="ml-auto text-muted">{usable ? s.count : n}</span>
            </label>
          );
        })}
      </fieldset>
    );
  }
  return (
    <section className="flex flex-col gap-2 rounded-2xl bg-tint p-3.5" aria-label="Stores searched">
      <h2 className="m-0 text-sm font-bold">Searched {live} stores</h2>
      <div className="flex flex-wrap gap-1.5 text-[13px]">
        {stores.map((s) => {
          const n = note(s);
          return n ? (
            <span key={s.platform} className="rounded-full border border-dashed border-muted bg-surface px-2.5 py-1 text-muted">
              {s.label} · {n}
            </span>
          ) : (
            <span key={s.platform} className="rounded-full bg-surface px-2.5 py-1">
              {s.label} {s.count}
            </span>
          );
        })}
      </div>
    </section>
  );
}
