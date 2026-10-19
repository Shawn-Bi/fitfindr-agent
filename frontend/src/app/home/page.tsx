"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { PhotoSearchButton } from "@/components/ComingSoon";
import { FilterBar } from "@/components/FilterBar";
import { ListingCard } from "@/components/ListingCard";
import { LogoMark } from "@/components/Logo";
import { RequireAuth } from "@/components/RequireAuth";
import { SearchBox } from "@/components/SearchBox";
import { ErrorBox, SkeletonGrid } from "@/components/States";
import { StoreBar } from "@/components/StoreBar";
import { api, ApiError } from "@/lib/api";
import { EMPTY_FILTERS, filtersToParams } from "@/lib/filters";
import { STYLE_COLORS, STYLES } from "@/lib/format";
import type { Pick, Profile, SearchFilters } from "@/lib/types";

interface HomeData {
  locked: boolean;
  closet_count: number;
  picks: Pick[];
  data_mode: string;
}

/** P4 Home: search, style cards, "Picked for your closet". */
function Home() {
  const [data, setData] = useState<HomeData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<SearchFilters>(EMPTY_FILTERS);
  const [touched, setTouched] = useState(false);

  // Pre-fill the filters from the profile (B4); sizes stay per category, so the search fills them in.
  useEffect(() => {
    api<Profile>("/profile")
      .then((p) =>
        setFilters((f) => ({
          ...f,
          min_price: p.budget_min,
          max_price: p.budget,
          gender: p.gender === "women" || p.gender === "men" ? p.gender : null,
        })),
      )
      .catch(() => undefined);
  }, []);

  /** Only filters the user changed go into the URL; the backend applies the profile itself. */
  const extraQuery = useMemo(() => {
    if (!touched) return "";
    const params = filtersToParams(filters);
    if (filters.min_price == null && filters.max_price == null) params.set("no_price", "1");
    if (filters.sizes != null && filters.sizes.length === 0) params.set("no_size", "1");
    return params.toString();
  }, [filters, touched]);

  const load = useCallback(() => {
    setError(null);
    api<HomeData>("/home")
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load your picks."));
  }, []);
  useEffect(load, [load]);

  return (
    <AppShell desktopSearch={false}>
      <div className="mx-auto max-w-[1200px] md:px-6">
        {/* Phone: logo · search · camera (prototype Home). Desktop: a bigger search block. */}
        <header className="flex items-center gap-2.5 px-4 pb-2 pt-4 md:hidden">
          <Link href="/home" aria-label="FitFindr home" className="flex shrink-0">
            <LogoMark size={38} />
          </Link>
          <SearchBox extraQuery={extraQuery} />
          <PhotoSearchButton />
        </header>
        <div className="px-4 pb-1 md:hidden">
          <FilterBar
            value={filters}
            onApply={(f) => {
              setFilters(f);
              setTouched(true);
            }}
            fromProfile={!touched && (filters.max_price != null || !!filters.gender)}
          />
        </div>
        <section className="hidden flex-col gap-3 pt-10 md:flex">
          <h1 className="m-0 font-heading text-[34px] font-bold tracking-[-0.8px]">What are you looking for?</h1>
          <div className="flex max-w-[760px] items-center gap-2.5">
            <SearchBox placeholder="vintage white shirt under $30" autoFocus extraQuery={extraQuery} />
            <PhotoSearchButton />
          </div>
          <FilterBar
            value={filters}
            onApply={(f) => {
              setFilters(f);
              setTouched(true);
            }}
            fromProfile={!touched && (filters.max_price != null || !!filters.gender)}
          />
        </section>
        <StoreBar className="px-4 pt-1 md:px-0 md:pt-3" />

        <section className="pt-5 md:pt-8" aria-labelledby="styles-title">
          <h2 id="styles-title" className="mx-4 mb-2.5 mt-0 font-heading text-lg font-bold md:mx-0 md:text-xl">
            Shop by style
          </h2>
          <div className="no-scrollbar flex gap-2.5 overflow-x-auto px-4 md:grid md:grid-cols-6 md:overflow-visible md:px-0">
            {STYLES.map((s) => (
              <Link
                key={s}
                href={`/search?q=${encodeURIComponent(s.toLowerCase())}${extraQuery ? `&${extraQuery}` : ""}`}
                style={{ background: STYLE_COLORS[s] }}
                className="flex h-[132px] w-28 shrink-0 items-end rounded-2xl p-3 font-heading text-[17px] font-bold text-white no-underline hover:text-white hover:brightness-110 md:h-[150px] md:w-auto"
              >
                {s}
              </Link>
            ))}
          </div>
        </section>

        <section className="px-4 pt-6 md:px-0 md:pt-10" aria-labelledby="picks-title">
          <div className="mb-2.5 flex items-baseline justify-between gap-3">
            <h2 id="picks-title" className="m-0 font-heading text-lg font-bold md:text-xl">
              Picked for your closet
            </h2>
            {data && !data.locked && (
              <Link href="/closet" className="text-sm font-bold">
                Your closet
              </Link>
            )}
          </div>
          {error && <ErrorBox message={error} onRetry={load} />}
          {!data && !error && <SkeletonGrid count={4} className="md:grid-cols-4" />}
          {data?.locked && (
            <div className="mb-4 flex flex-col gap-2 rounded-2xl bg-tint p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="font-bold">Add items to unlock picks for your closet</div>
                <div className="text-sm text-muted">
                  Once you add a few pieces, we&apos;ll suggest finds that go with them.
                </div>
              </div>
              <Link
                href="/closet/new"
                className="flex h-11 shrink-0 items-center justify-center rounded-xl bg-primary px-4 font-bold text-white no-underline hover:bg-primary-hover hover:text-white"
              >
                Add your first item
              </Link>
            </div>
          )}
          {data?.locked && data.picks.length > 0 && (
            <h3 className="mb-2.5 mt-0 text-[15px] font-bold">Fresh finds from each store</h3>
          )}
          {data && data.picks.length > 0 && (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
              {data.picks.map((p) => (
                <ListingCard key={`${p.listing.platform}-${p.listing.id}`} listing={p.listing} reason={p.reason} />
              ))}
            </div>
          )}
          {data && data.picks.length === 0 && (
            <p className="m-0 rounded-2xl bg-surface p-4 text-sm text-muted">
              No picks right now. Picks come from recent searches, so try a search above and check back.
            </p>
          )}
          {data && data.picks.length > 0 && (
            <p className="mb-0 mt-3 text-xs text-muted">Price and stock may change on the original site.</p>
          )}
        </section>
      </div>
    </AppShell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Home />
    </RequireAuth>
  );
}
