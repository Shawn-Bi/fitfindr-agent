"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/components/AuthProvider";
import { BackIcon, ExternalIcon } from "@/components/Icons";
import { ListingCard, ListingImage, SaveButton } from "@/components/ListingCard";
import { SearchBox } from "@/components/SearchBox";
import { ErrorBox, Spinner } from "@/components/States";
import { StorePanel } from "@/components/StoreBar";
import { api, ApiError } from "@/lib/api";
import { cleanTitle, money, STORE_LABELS, timeAgo } from "@/lib/format";
import type { Chip, Listing, SearchResponse } from "@/lib/types";

function useSearchState() {
  const params = useSearchParams();
  return {
    q: params.get("q") || "",
    no_size: params.get("no_size") === "1",
    no_price: params.get("no_price") === "1",
    max_price: params.get("max") ? Number(params.get("max")) : null,
  };
}

function buildUrl(s: { q: string; no_size?: boolean; no_price?: boolean; max_price?: number | null }) {
  const p = new URLSearchParams({ q: s.q });
  if (s.no_size) p.set("no_size", "1");
  if (s.no_price) p.set("no_price", "1");
  if (s.max_price != null) p.set("max", String(s.max_price));
  return `/search?${p.toString()}`;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        } catch {
          setCopied(false);
        }
      }}
      className="h-11 shrink-0 rounded-[10px] border-[1.5px] border-ink bg-surface px-3 text-[13px] font-bold hover:bg-tint"
    >
      <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

function Chips({ chips, onRemove }: { chips: Chip[]; onRemove: (c: Chip) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map((c) => (
        <button
          key={c.key}
          type="button"
          onClick={() => onRemove(c)}
          aria-label={`Remove filter ${c.label}${c.from_profile ? " from your profile" : ""}`}
          className={`flex h-11 items-center gap-1.5 rounded-full pl-3 pr-2.5 text-[13px] md:h-9 ${
            c.from_profile ? "border-[1.5px] border-dashed border-ink bg-surface text-ink" : "border-0 bg-ink text-white"
          }`}
        >
          {c.label}
          {c.from_profile && " · from profile"}
          <span aria-hidden="true" className="text-base leading-none">
            ×
          </span>
        </button>
      ))}
    </div>
  );
}

function BestMatch({ item, data }: { item: Listing; data: SearchResponse }) {
  const store = STORE_LABELS[item.platform];
  const updated = timeAgo(item.updated_at);
  const meta = [item.size, item.condition, store, updated && `updated ${updated}`].filter(Boolean).join(" · ");
  const styling = data.styling;
  const title = cleanTitle(item.title);
  return (
    <article className="flex flex-col overflow-hidden rounded-[18px] bg-surface md:flex-row" aria-labelledby="best-title">
      <div className="relative md:w-[44%] md:shrink-0">
        <ListingImage listing={item} className="h-[260px] w-full md:h-full md:min-h-[380px]" />
        <span className="absolute left-2.5 top-2.5 rounded-full bg-ink px-2.5 py-1 text-[11px] font-bold text-white md:text-xs">
          Best match
        </span>
        <span className="absolute right-14 top-2.5 rounded-full bg-surface px-2.5 py-1 text-[11px] font-bold md:hidden">
          {store}
        </span>
        <div className="absolute right-1 top-1 md:hidden">
          <SaveButton listing={item} saved={item.saved} />
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-3 px-4 pb-4 pt-3.5 md:gap-3.5 md:px-[22px] md:py-5">
        <div className="flex justify-between gap-2.5">
          <div className="min-w-0">
            <h2 id="best-title" className="m-0 text-[17px] font-bold leading-tight md:text-[22px]">
              {title}
            </h2>
            <div className="mt-[3px] text-[13px] text-muted md:text-sm">{meta}</div>
          </div>
          <div className="shrink-0 font-heading text-2xl font-bold md:text-[30px]">{money(item.price)}</div>
        </div>

        <div className="flex flex-col gap-2.5 rounded-[14px] bg-bg p-3 md:p-3.5">
          <h3 className="m-0 text-[13px] font-bold md:text-sm">
            {data.personalized ? "How to wear it with your closet" : "How to wear it"}
          </h3>
          {styling?.items && styling.items.length > 0 && (
            <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
              {styling.items.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/closet/${c.id}`}
                    className="flex w-[72px] flex-col gap-1 text-[11px] leading-tight text-ink no-underline hover:text-primary md:w-[78px] md:text-xs"
                  >
                    {c.thumb ? (
                      // eslint-disable-next-line @next/next/no-img-element -- signed Supabase URL
                      <img src={c.thumb} alt={`Your ${c.name}`} className="h-[72px] w-[72px] rounded-[10px] object-cover md:h-[78px] md:w-[78px]" />
                    ) : (
                      <span className="h-[72px] w-[72px] rounded-[10px] bg-line-soft" />
                    )}
                    <span className="line-clamp-2">{c.name}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {styling?.unavailable ? (
            <p className="m-0 text-[13px] text-muted">{styling.unavailable}</p>
          ) : (
            <p className="m-0 text-[13px] leading-[1.45] md:text-sm md:leading-normal">{styling?.text}</p>
          )}
          {!data.signed_in && (
            <p className="m-0 text-[13px]">
              <Link href="/signup" className="font-bold">
                Sign up
              </Link>{" "}
              to style finds with your own closet.
            </p>
          )}
          {data.signed_in && !data.personalized && (
            <p className="m-0 text-[13px]">
              <Link href="/closet/new" className="font-bold">
                Add closet items
              </Link>{" "}
              to get outfit ideas with your own clothes.
            </p>
          )}
        </div>

        {data.fit_card && (
          <div className="flex flex-col gap-2 rounded-[14px] border-[1.5px] border-dashed border-line-dash p-3 md:flex-row md:items-start md:gap-3 md:px-3.5">
            <div className="flex items-center justify-between md:hidden">
              <span className="text-[13px] font-bold">Fit card</span>
              <CopyButton text={data.fit_card} />
            </div>
            <p className="m-0 flex-1 text-[13px] leading-[1.45] text-ink-soft md:text-sm md:leading-normal">
              <strong className="hidden md:inline">Fit card: </strong>
              {data.fit_card}
            </p>
            <div className="hidden md:block">
              <CopyButton text={data.fit_card} />
            </div>
          </div>
        )}

        <div className="flex gap-2.5">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex h-[50px] flex-1 items-center justify-center gap-2 rounded-[14px] bg-primary text-[15px] font-bold text-white no-underline hover:bg-primary-hover hover:text-white md:h-12 md:rounded-xl"
          >
            View on {store} <ExternalIcon />
            <span className="sr-only">(opens in a new tab)</span>
          </a>
          <div className="hidden md:block">
            <SaveButton listing={item} saved={item.saved} variant="outline" />
          </div>
        </div>
        <div className="text-center text-[11px] text-muted md:text-left md:text-xs">
          Price and stock may change on the original site.
        </div>
      </div>
    </article>
  );
}

function Results() {
  const router = useRouter();
  const state = useSearchState();
  const { loading: authLoading, session } = useAuth();
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const key = `${state.q}|${state.no_size}|${state.no_price}|${state.max_price}|${session?.user.id || ""}`;

  const run = useCallback(
    (signal?: AbortSignal) => {
      if (!state.q) return;
      setBusy(true);
      setError(null);
      setHidden(new Set());
      api<SearchResponse>("/search", {
        json: { q: state.q, no_size: state.no_size, no_price: state.no_price, max_price: state.max_price },
        signal,
      })
        .then((d) => {
          setData(d);
          setBusy(false);
        })
        .catch((e) => {
          if ((e as Error).name === "AbortError") return;
          setError(e instanceof ApiError ? e.message : "Search failed. Please try again.");
          setBusy(false);
        });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` captures every input
    [key],
  );

  useEffect(() => {
    if (authLoading) return;
    const ctrl = new AbortController();
    run(ctrl.signal);
    return () => ctrl.abort();
  }, [run, authLoading]);

  function removeChip(c: Chip) {
    if (c.key === "q") return router.push(session ? "/home" : "/");
    if (c.key === "size") return router.push(buildUrl({ ...state, no_size: true }));
    if (c.key === "price") return router.push(buildUrl({ ...state, no_price: true, max_price: null }));
  }

  function relax(params: Record<string, unknown>) {
    router.push(
      buildUrl({
        ...state,
        no_size: params.no_size ? true : state.no_size,
        max_price: typeof params.max_price === "number" ? params.max_price : state.max_price,
        no_price: typeof params.max_price === "number" ? false : state.no_price,
      }),
    );
  }

  const best = data?.results[0];
  const more = useMemo(
    () => (data?.results.slice(1) || []).filter((r) => !hidden.has(r.platform)),
    [data, hidden],
  );
  const toggleStore = (p: string) => {
    const next = new Set(hidden);
    if (next.has(p)) next.delete(p);
    else next.add(p);
    setHidden(next);
  };

  return (
    <AppShell searchInitial={state.q}>
      <div className="mx-auto max-w-[1200px] md:px-6">
        <header className="flex items-center gap-1.5 pb-1.5 pl-1 pr-3 pt-3 md:hidden">
          <Link
            href={session ? "/home" : "/"}
            aria-label="Back"
            className="flex h-11 w-11 shrink-0 items-center justify-center text-ink"
          >
            <BackIcon />
          </Link>
          <SearchBox initial={state.q} placeholder="vintage graphic tee under $30" />
        </header>

        {!state.q && (
          <div className="px-4 pt-6 md:px-0">
            <h1 className="m-0 font-heading text-2xl font-bold">What are you looking for?</h1>
            <p className="text-muted">Describe it in plain words, like &ldquo;vintage graphic tee under $30&rdquo;.</p>
          </div>
        )}

        {state.q && (
          <>
            <div className="flex flex-col gap-2 px-4 pt-1 md:flex-row md:flex-wrap md:items-center md:px-0 md:pt-5">
              <div className="text-xs text-muted md:mr-1 md:text-[13px]">
                {data ? `FitFindr searched ${data.stores.filter((s) => s.status === "live").length} stores for` : "Searching for"}
              </div>
              {data && <Chips chips={data.chips} onRemove={removeChip} />}
            </div>

            {busy && (
              <div className="flex flex-col gap-2 px-4 py-10 md:px-0" aria-live="polite">
                <Spinner label="Searching stores and styling the best match" />
                <p className="m-0 text-sm text-muted">This can take a few seconds.</p>
              </div>
            )}
            {error && !busy && (
              <div className="px-4 pt-4 md:px-0">
                <ErrorBox message={error} onRetry={() => run()} />
              </div>
            )}

            {data && !busy && !error && (
              <div className="mt-3.5 flex flex-col gap-5 md:mt-5 md:flex-row md:items-start">
                <div className="flex min-w-0 flex-1 flex-col gap-[18px] px-4 md:px-0">
                  {data.empty ? (
                    <section className="flex flex-col gap-3 rounded-[18px] bg-surface p-5" aria-live="polite">
                      <h1 className="m-0 font-heading text-xl font-bold">No matches yet</h1>
                      <p className="m-0 text-[15px]">{data.empty.message}</p>
                      {data.empty.relax.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {data.empty.relax.map((r) => (
                            <button
                              key={r.label}
                              type="button"
                              onClick={() => relax(r.params)}
                              className="h-11 rounded-xl bg-primary px-4 font-bold text-white hover:bg-primary-hover"
                            >
                              {r.label}
                            </button>
                          ))}
                        </div>
                      )}
                      <p className="m-0 text-sm text-muted">Or try different words — fewer, broader terms usually find more.</p>
                    </section>
                  ) : (
                    best && <BestMatch item={best} data={data} />
                  )}

                  {more.length > 0 && (
                    <section aria-labelledby="more-title">
                      <h2 id="more-title" className="mb-2.5 mt-0 font-heading text-[17px] font-bold md:mb-3 md:text-lg">
                        More matches · {more.length}
                      </h2>
                      <div className="grid grid-cols-2 gap-3 md:grid-cols-[repeat(auto-fill,minmax(180px,1fr))] md:gap-3.5">
                        {more.map((r) => (
                          <ListingCard key={`${r.platform}-${r.id}`} listing={r} imageHeight="h-[120px] md:h-[170px]" />
                        ))}
                      </div>
                      <p className="mb-0 mt-2 text-xs text-muted">Price and stock may change on the original site.</p>
                    </section>
                  )}

                  <div className="md:hidden">
                    <StorePanel stores={data.stores} />
                    {data.stores.some((s) => s.status === "live" && s.count > 0) && more.length + hidden.size > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-label="Show stores">
                        {data.stores
                          .filter((s) => s.status === "live" && s.count > 0)
                          .map((s) => (
                            <button
                              key={s.platform}
                              type="button"
                              aria-pressed={!hidden.has(s.platform)}
                              onClick={() => toggleStore(s.platform)}
                              className={`h-11 rounded-full border-[1.5px] px-3 text-[13px] ${
                                hidden.has(s.platform) ? "border-line bg-surface text-muted line-through" : "border-ink bg-surface"
                              }`}
                            >
                              {s.label}
                            </button>
                          ))}
                      </div>
                    )}
                  </div>
                </div>

                <aside className="hidden w-[300px] shrink-0 flex-col gap-3.5 md:flex">
                  <StorePanel stores={data.stores} variant="filters" hidden={hidden} onToggle={toggleStore} />
                  <section className="flex flex-col gap-2 rounded-2xl bg-surface p-4">
                    <h2 className="m-0 text-[15px] font-bold">
                      {data.personalized ? "Matched to your closet" : "Style it with your closet"}
                    </h2>
                    <p className="m-0 text-[13px] leading-normal text-muted">
                      {data.personalized ? (
                        <>
                          Ranked using your {data.closet_count} closet items
                          {data.parsed.size ? `, size ${data.parsed.size}` : ""}
                          {data.parsed.max_price != null ? ` and a ${money(data.parsed.max_price)} budget` : ""}.{" "}
                          <Link href="/profile">Edit preferences</Link>
                        </>
                      ) : data.signed_in ? (
                        <>
                          <Link href="/closet/new">Add closet items</Link> and FitFindr will suggest outfits with your own
                          clothes.
                        </>
                      ) : (
                        <>
                          <Link href="/signup">Sign up</Link> to get outfit ideas using the clothes you already own.
                        </>
                      )}
                    </p>
                  </section>
                </aside>
              </div>
            )}
            {data?.data_mode === "fixtures" && !busy && (
              <p className="mx-4 mb-0 mt-6 text-xs text-muted md:mx-0">
                Development mode: these are recorded responses from the stores, not a live search.
              </p>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Results />
    </Suspense>
  );
}
