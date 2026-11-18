"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { PlusIcon, ShirtIcon } from "@/components/Icons";
import { RequireAuth } from "@/components/RequireAuth";
import { ErrorBox, SkeletonGrid } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import { CATEGORIES } from "@/lib/format";
import type { ClosetItem } from "@/lib/types";

interface ClosetData {
  items: ClosetItem[];
  counts: Record<string, number>;
  total: number;
}

function AddButton({ label = "Add item" }: { label?: string }) {
  return (
    <Link
      href="/closet/new"
      className="flex h-11 shrink-0 items-center gap-1.5 rounded-xl bg-primary px-4 text-[15px] font-bold text-white no-underline hover:bg-primary-hover hover:text-white"
    >
      <PlusIcon /> {label}
    </Link>
  );
}

/** P6 My Closet: count, search, category tabs, photo grid. */
function Closet() {
  const [data, setData] = useState<ClosetData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<string>("all");
  const [q, setQ] = useState("");

  const load = useCallback(() => {
    setError(null);
    api<ClosetData>("/closet/items")
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load your closet."));
  }, []);
  useEffect(load, [load]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data?.items || []).filter(
      (i) =>
        (tab === "all" || i.category === tab) &&
        (!needle ||
          [i.name, i.brand, ...i.colors, ...i.style_tags].filter(Boolean).join(" ").toLowerCase().includes(needle)),
    );
  }, [data, tab, q]);

  const tabs = [{ key: "all", label: "All", count: data?.total ?? 0 }].concat(
    CATEGORIES.map((c) => ({ key: c.key, label: c.label, count: data?.counts[c.key] ?? 0 })),
  );

  return (
    <AppShell>
      <div className="mx-auto max-w-[1200px] md:flex md:gap-7 md:px-6 md:pt-6">
        <aside className="hidden w-[220px] shrink-0 md:block" aria-labelledby="cat-title">
          <h2 id="cat-title" className="mb-2 mt-0 text-[15px] font-bold">
            Categories
          </h2>
          <nav className="flex flex-col gap-0.5">
            {tabs.map((t) => (
              <button
                key={t.key}
                type="button"
                aria-current={tab === t.key ? "true" : undefined}
                onClick={() => setTab(t.key)}
                className={`flex h-11 items-center justify-between rounded-[10px] px-3 text-left ${
                  tab === t.key ? "bg-tint font-bold text-primary-hover" : "hover:bg-surface"
                }`}
              >
                {t.label}
                <span className={tab === t.key ? "" : "text-muted"}>{t.count}</span>
              </button>
            ))}
          </nav>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="flex items-end justify-between gap-3 px-4 pb-2.5 pt-5 md:px-0 md:pt-0">
            <div>
              <h1 className="m-0 font-heading text-[28px] font-bold tracking-[-0.5px]">My Closet</h1>
              <div className="text-[13px] text-muted">
                {data ? `${data.total} item${data.total === 1 ? "" : "s"} · ` : ""}only you can see this
              </div>
            </div>
            <AddButton />
          </header>

          {error && (
            <div className="px-4 md:px-0">
              <ErrorBox message={error} onRetry={load} />
            </div>
          )}
          {!data && !error && <SkeletonGrid count={6} className="px-4 md:grid-cols-4 md:px-0" />}

          {data && data.total === 0 && (
            <section className="mx-4 mt-4 flex flex-col items-center gap-3 rounded-[18px] bg-surface px-6 py-10 text-center md:mx-0">
              <span className="text-line">
                <ShirtIcon size={56} />
              </span>
              <h2 className="m-0 font-heading text-xl font-bold">Your closet starts here</h2>
              <p className="m-0 max-w-[340px] text-sm text-muted">
                Add a few pieces you wear a lot. FitFindr uses them to style every find with clothes you already own.
              </p>
              <AddButton label="Add your first item" />
            </section>
          )}

          {data && data.total > 0 && (
            <>
              <div className="px-4 md:px-0">
                <label htmlFor="closet-search" className="sr-only">
                  Search your closet
                </label>
                <input
                  id="closet-search"
                  type="search"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search your closet"
                  className="h-11 w-full rounded-xl border-[1.5px] border-line bg-surface px-3.5 text-[15px] outline-none focus:border-primary"
                />
              </div>
              <div role="tablist" aria-label="Categories" className="no-scrollbar flex gap-2 overflow-x-auto px-4 pb-1 pt-3 md:hidden">
                {tabs.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    role="tab"
                    aria-selected={tab === t.key}
                    onClick={() => setTab(t.key)}
                    className={`h-11 shrink-0 rounded-full px-3.5 text-sm ${
                      tab === t.key ? "bg-ink font-bold text-white" : "border-[1.5px] border-line bg-surface text-ink"
                    }`}
                  >
                    {t.label} {t.count}
                  </button>
                ))}
              </div>
              <div className="grid grid-cols-3 gap-2 px-4 pt-3 md:grid-cols-4 md:gap-3.5 md:px-0 lg:grid-cols-5">
                {shown.map((item) => (
                  <Link
                    key={item.id}
                    href={`/closet/${item.id}`}
                    className="flex flex-col gap-1 text-ink no-underline hover:text-primary"
                  >
                    {item.thumb ? (
                      // eslint-disable-next-line @next/next/no-img-element -- signed Supabase URL
                      <img
                        src={item.thumb}
                        alt={item.name}
                        loading="lazy"
                        className="aspect-[4/5] w-full rounded-xl bg-line-soft object-cover"
                      />
                    ) : (
                      <span className="aspect-[4/5] w-full rounded-xl bg-line-soft" />
                    )}
                    <span className="line-clamp-2 text-xs leading-tight md:text-sm">{item.name}</span>
                  </Link>
                ))}
                <Link
                  href="/closet/new"
                  className="hidden aspect-[4/5] flex-col items-center justify-center gap-1 rounded-xl border-[1.5px] border-dashed border-line text-sm font-bold text-primary no-underline md:flex"
                >
                  <PlusIcon size={24} /> Add item
                </Link>
              </div>
              {shown.length === 0 && (
                <p className="px-4 text-sm text-muted md:px-0">Nothing in your closet matches that. Try another word or category.</p>
              )}
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Closet />
    </RequireAuth>
  );
}
