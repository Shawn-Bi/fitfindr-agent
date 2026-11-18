"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { HeartIcon } from "@/components/Icons";
import { ListingImage, SaveButton } from "@/components/ListingCard";
import { RequireAuth } from "@/components/RequireAuth";
import { ErrorBox, SkeletonGrid } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import { cleanTitle, listingMeta, money, shortDate, STORE_LABELS } from "@/lib/format";
import type { SavedRow } from "@/lib/types";

/** P9 Saved: snapshots of saved listings (DECISIONS.md #24). */
function Saved() {
  const [rows, setRows] = useState<SavedRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api<{ items: SavedRow[] }>("/saved")
      .then((d) => setRows(d.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load your saved items."));
  }, []);
  useEffect(load, [load]);

  const visible = (rows || []).filter((r) => r.listing);

  return (
    <AppShell>
      <div className="mx-auto max-w-[1200px] px-4 md:px-6 md:pt-6">
        <header className="pb-3 pt-5 md:pt-0">
          <h1 className="m-0 font-heading text-[28px] font-bold tracking-[-0.5px]">Saved</h1>
          <div className="text-[13px] text-muted">
            {rows ? `${visible.length} item${visible.length === 1 ? "" : "s"} · ` : ""}prices may have changed since you saved them
          </div>
        </header>
        {error && <ErrorBox message={error} onRetry={load} />}
        {!rows && !error && <SkeletonGrid count={4} className="md:grid-cols-4" />}
        {rows && visible.length === 0 && (
          <section className="flex flex-col items-center gap-3 rounded-[18px] bg-surface px-6 py-10 text-center">
            <span className="text-line">
              <HeartIcon size={48} />
            </span>
            <h2 className="m-0 font-heading text-xl font-bold">Nothing saved yet</h2>
            <p className="m-0 max-w-[320px] text-sm text-muted">Tap the heart on any find to keep it here.</p>
            <Link
              href="/home"
              className="flex h-11 items-center rounded-xl bg-primary px-4 font-bold text-white no-underline hover:bg-primary-hover hover:text-white"
            >
              Start searching
            </Link>
          </section>
        )}
        {visible.length > 0 && (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
            {visible.map((r) => {
              const l = r.listing!;
              const gone = !r.available;
              return (
                <article key={`${r.source}-${r.listing_id}`} className={`relative flex flex-col overflow-hidden rounded-2xl bg-surface ${gone ? "opacity-60 grayscale" : ""}`}>
                  <a href={l.url} target="_blank" rel="noopener noreferrer" className="flex flex-1 flex-col text-ink no-underline hover:text-ink">
                    <ListingImage listing={l} className="h-[150px] w-full md:h-[190px]" />
                    <div className="flex flex-col gap-[3px] px-3 pb-3 pt-2.5">
                      {gone && <div className="text-xs font-bold text-danger">No longer available</div>}
                      <h2 className="m-0 line-clamp-2 text-sm font-bold leading-tight">{cleanTitle(l.title)}</h2>
                      <div className="text-[13px] text-muted">{listingMeta(l)}</div>
                      <div className="text-base font-bold">{money(l.price)}</div>
                      <div className="text-xs text-muted">Saved on {shortDate(r.saved_at)} · price may have changed</div>
                      <span className="sr-only">Opens on {STORE_LABELS[l.platform]} in a new tab</span>
                    </div>
                  </a>
                  <div className="absolute right-1 top-1">
                    <SaveButton
                      listing={l}
                      saved
                      onChange={(s) => !s && setRows((prev) => (prev || []).filter((x) => x !== r))}
                    />
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Saved />
    </RequireAuth>
  );
}
