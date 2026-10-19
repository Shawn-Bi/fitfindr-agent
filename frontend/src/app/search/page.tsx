"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { BuyerVerdict } from "@/components/BuyerVerdict";
import { FilterBar } from "@/components/FilterBar";
import { useAuth } from "@/components/AuthProvider";
import { BackIcon, ExternalIcon } from "@/components/Icons";
import { ListingCard, ListingImage, SaveButton } from "@/components/ListingCard";
import { OutfitCollage, type CollageTile } from "@/components/OutfitCollage";
import { SearchBox } from "@/components/SearchBox";
import { ErrorBox, Spinner } from "@/components/States";
import { StorePanel } from "@/components/StoreBar";
import { api, ApiError } from "@/lib/api";
import { filtersFromParams, filtersToBody, filtersToParams } from "@/lib/filters";
import { cleanTitle, money, STORE_LABELS, timeAgo } from "@/lib/format";
import type { Chip, Listing, SearchFilters, SearchResponse, StyleResponse } from "@/lib/types";

interface SearchState {
  q: string;
  no_size: boolean;
  no_price: boolean;
  filters: SearchFilters;
}

function useSearchState(): SearchState {
  const params = useSearchParams();
  return {
    q: params.get("q") || "",
    no_size: params.get("no_size") === "1",
    no_price: params.get("no_price") === "1",
    filters: filtersFromParams(params),
  };
}

function buildUrl(s: SearchState) {
  const p = new URLSearchParams({ q: s.q });
  if (s.no_size) p.set("no_size", "1");
  if (s.no_price) p.set("no_price", "1");
  filtersToParams(s.filters, p);
  return `/search?${p.toString()}`;
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

function BestMatch({ item, data, styling: stylingBusy }: { item: Listing; data: SearchResponse; styling: boolean }) {
  const store = STORE_LABELS[item.platform];
  const updated = timeAgo(item.updated_at);
  const size = item.size ?? (data.parsed.size ? "size not listed" : null);
  const meta = [size, item.condition, store, updated && `updated ${updated}`].filter(Boolean).join(" · ");
  const styling = data.styling;
  const title = cleanTitle(item.title);
  const tiles: CollageTile[] = [
    { src: item.image_url, alt: title, badge: store, kind: "find" },
    ...(styling?.items || []).slice(0, 3).map(
      (c): CollageTile => ({ src: c.photo || c.thumb, alt: `Your ${c.name}`, badge: "Yours", kind: "closet" }),
    ),
  ];
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
      <div className="flex min-w-0 flex-1 flex-col gap-3 px-4 pb-4 pt-3.5 md:gap-3.5 md:px-[22px] md:py-5">
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
          {tiles.length > 1 && (
            <OutfitCollage tiles={tiles} label={`Outfit: ${title} with your closet pieces`} className="max-w-[420px]" />
          )}
          {styling?.items && styling.items.length > 0 && (
            <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
              {styling.items.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/closet/${c.id}`}
                    className="flex min-h-11 items-center rounded-full bg-surface px-3 text-xs font-bold text-ink no-underline hover:text-primary"
                  >
                    Your {c.name}
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {stylingBusy && !styling ? (
            <Spinner label="Styling this find with your closet" />
          ) : styling?.unavailable ? (
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

        {data.fit_card && <BuyerVerdict verdict={data.fit_verdict || null} caption={data.fit_card} price={item.price} />}

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

/** The agent's one clarifying question (A1), with tap-to-answer suggestions. */
function Clarify({ question, suggestions, onAnswer }: { question: string; suggestions: string[]; onAnswer: (q: string) => void }) {
  const [answer, setAnswer] = useState("");
  return (
    <section className="flex flex-col gap-3 rounded-[18px] bg-surface p-5" aria-live="polite" aria-labelledby="clarify-title">
      <div className="text-xs font-bold uppercase tracking-wide text-primary">One quick question</div>
      <h1 id="clarify-title" className="m-0 font-heading text-xl font-bold">
        {question}
      </h1>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onAnswer(s)}
            className="h-11 rounded-full border-[1.5px] border-ink bg-surface px-4 text-sm font-bold hover:bg-tint"
          >
            {s}
          </button>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (answer.trim()) onAnswer(answer.trim());
        }}
        className="flex gap-2"
      >
        <label htmlFor="clarify-answer" className="sr-only">
          Your answer
        </label>
        <input
          id="clarify-answer"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Or type it, e.g. a camel wool coat"
          maxLength={200}
          className="h-12 min-w-0 flex-1 rounded-xl border-[1.5px] border-line bg-surface px-3.5 text-base outline-none focus:border-primary"
        />
        <button type="submit" className="h-12 rounded-xl bg-primary px-4 font-bold text-white hover:bg-primary-hover">
          Search
        </button>
      </form>
    </section>
  );
}

function Results() {
  const router = useRouter();
  const state = useSearchState();
  const { loading: authLoading, session } = useAuth();
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [styling, setStyling] = useState(false);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  // A filter or chip change re-searches at once with style=false (no model
  // calls); a new query, a refresh or a back/forward visit runs the full agent.
  const quickNext = useRef(false);
  const dataRef = useRef<SearchResponse | null>(null);
  dataRef.current = data;
  const key = `${buildUrl(state)}|${session?.user.id || ""}`;

  /** Styling + fit card for the best match after a quick search; reused when the best match didn't change. */
  const styleBest = useCallback((d: SearchResponse, previous: SearchResponse | null, signal: AbortSignal) => {
    const best = d.results[0];
    if (!d.styling_deferred || !best) return;
    const prevBest = previous?.results[0];
    if (prevBest && previous?.styling && prevBest.platform === best.platform && prevBest.id === best.id) {
      setData({ ...d, styling: previous.styling, fit_card: previous.fit_card, fit_verdict: previous.fit_verdict });
      return;
    }
    setStyling(true);
    api<StyleResponse>("/search/style", { json: { q: d.query, listing: best }, signal })
      .then((r) => setData((cur) => (cur && cur.results[0]?.id === best.id ? { ...cur, ...r } : cur)))
      .catch(() => undefined)
      .finally(() => setStyling(false));
  }, []);

  const run = useCallback(
    (signal?: AbortSignal) => {
      if (!state.q) return;
      const previous = dataRef.current;
      const quick = quickNext.current && previous != null && previous.query === state.q && !previous.clarify;
      quickNext.current = false;
      setBusy(true);
      setError(null);
      if (!quick) setHidden(new Set());
      const ctrl = new AbortController();
      signal?.addEventListener("abort", () => ctrl.abort());
      api<SearchResponse>("/search", {
        json: {
          q: state.q,
          no_size: state.no_size,
          no_price: state.no_price,
          ...filtersToBody(state.filters),
          style: !quick,
        },
        signal: ctrl.signal,
      })
        .then((d) => {
          setData(d);
          setBusy(false);
          styleBest(d, previous, ctrl.signal);
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
    // Quick searches wait for a short pause, so several chip taps make one search.
    const t = setTimeout(() => run(ctrl.signal), quickNext.current ? 300 : 0);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [run, authLoading]);

  /** Filters live in the URL (refresh and back keep them); replace, so each tap isn't a history entry. */
  function go(next: SearchState) {
    quickNext.current = true;
    router.replace(buildUrl(next), { scroll: false });
  }

  function removeChip(c: Chip) {
    if (c.key === "q") return router.push(session ? "/home" : "/");
    if (c.key === "size") return go({ ...state, no_size: true, filters: { ...state.filters, sizes: null } });
    if (c.key === "price")
      return go({ ...state, no_price: true, filters: { ...state.filters, min_price: null, max_price: null } });
  }

  function relax(params: Record<string, unknown>) {
    go({
      ...state,
      no_size: params.no_size ? true : state.no_size,
      no_price: typeof params.max_price === "number" ? false : state.no_price,
      filters: {
        ...state.filters,
        sizes: params.no_size ? null : state.filters.sizes,
        max_price: typeof params.max_price === "number" ? params.max_price : state.filters.max_price,
      },
    });
  }

  function applyFilters(next: SearchFilters) {
    // Explicit filters replace the profile's; clearing a price or size means "none".
    go({
      ...state,
      no_size: next.sizes != null && next.sizes.length === 0,
      no_price: next.min_price == null && next.max_price == null,
      filters: next,
    });
  }

  const shownFilters: SearchFilters = useMemo(() => {
    const f = data?.filters;
    if (!f) return state.filters;
    return {
      min_price: f.min_price,
      max_price: f.max_price,
      sizes: f.sizes,
      conditions: f.conditions,
      colors: f.colors,
      gender: f.gender,
      within_days: f.within_days,
      stores: f.stores,
      location: state.filters.location,
    };
  }, [data, state.filters]);

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
                {data && !data.clarify
                  ? `FitFindr searched ${data.stores.filter((s) => s.status === "live").length} stores for`
                  : "Searching for"}
              </div>
              {data && !data.clarify && <Chips chips={data.chips} onRemove={removeChip} />}
            </div>
            <div className="px-4 pt-2 md:px-0 md:pt-3">
              <FilterBar
                value={shownFilters}
                support={data?.filter_support}
                onChange={applyFilters}
                fromProfile={!!data?.chips.some((c) => c.from_profile)}
                resultCount={data && !data.clarify ? data.results.length : null}
                busy={busy}
              />
            </div>

            {busy && !data && (
              <div className="flex flex-col gap-2 px-4 py-10 md:px-0" aria-live="polite">
                <Spinner label="Searching stores and styling the best match" />
                <p className="m-0 text-sm text-muted">This can take a few seconds.</p>
              </div>
            )}
            {busy && data && (
              <div className="px-4 pt-3 md:px-0" aria-live="polite">
                <Spinner label="Updating results" />
              </div>
            )}
            {error && !busy && (
              <div className="px-4 pt-4 md:px-0">
                <ErrorBox message={error} onRetry={() => run()} />
              </div>
            )}

            {data && !error && (
              <div
                className={`mt-3.5 flex flex-col gap-5 transition-opacity md:mt-5 md:flex-row md:items-start ${busy ? "opacity-60" : ""}`}
                aria-busy={busy}
              >
                <div className="flex min-w-0 flex-1 flex-col gap-[18px] px-4 md:px-0">
                  {data.broadened && !data.empty && (
                    <div role="status" className="flex items-start gap-2 rounded-xl bg-tint p-3 text-sm">
                      <span aria-hidden="true" className="font-bold text-primary-hover">
                        ↔
                      </span>
                      <span>{data.broadened.message}</span>
                    </div>
                  )}
                  {data.relaxed && (
                    <div role="status" className="flex items-start gap-2 rounded-xl bg-tint p-3 text-sm">
                      <span aria-hidden="true" className="font-bold text-primary-hover">
                        ↻
                      </span>
                      <span>
                        {data.relaxed.message}{" "}
                        <span className="text-muted">FitFindr changed only this one filter.</span>
                      </span>
                    </div>
                  )}
                  {data.clarify ? (
                    <Clarify
                      question={data.clarify.question}
                      suggestions={data.clarify.suggestions}
                      onAnswer={(q) => router.push(buildUrl({ ...state, q }))}
                    />
                  ) : data.empty ? (
                    <section className="flex flex-col gap-3 rounded-[18px] bg-surface p-5" aria-live="polite">
                      <h1 className="m-0 font-heading text-xl font-bold">{data.empty.title || "No matches yet"}</h1>
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
                    best && <BestMatch item={best} data={data} styling={styling} />
                  )}

                  {more.length > 0 && (
                    <section aria-labelledby="more-title">
                      <h2 id="more-title" className="mb-2.5 mt-0 font-heading text-[17px] font-bold md:mb-3 md:text-lg">
                        More matches · {more.length}
                      </h2>
                      <div className="grid grid-cols-2 gap-3 md:grid-cols-[repeat(auto-fill,minmax(180px,1fr))] md:gap-3.5">
                        {more.map((r) => (
                          <ListingCard
                            key={`${r.platform}-${r.id}`}
                            listing={r}
                            imageHeight="h-[120px] md:h-[170px]"
                            noteMissingSize={!!data.parsed.size}
                          />
                        ))}
                      </div>
                      <p className="mb-0 mt-2 text-xs text-muted">Price and stock may change on the original site.</p>
                    </section>
                  )}

                  {!data.clarify && (
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
                  )}
                </div>

                {!data.clarify && (
                  <aside className="hidden w-[300px] shrink-0 flex-col gap-3.5 md:flex">
                    <StorePanel stores={data.stores} variant="filters" hidden={hidden} onToggle={toggleStore} />
                    <section className="flex flex-col gap-2 rounded-2xl bg-surface p-4">
                      <h2 className="m-0 text-[15px] font-bold">
                        {data.personalized ? "Matched to your closet" : "Style it with your closet"}
                      </h2>
                      <p className="m-0 text-[13px] leading-normal text-muted">
                        {data.personalized ? (
                          <>
                            Ranked by meaning, not just keywords, using your {data.closet_count} closet items
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
                )}
              </div>
            )}
            {data?.data_mode === "fixtures" && (
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
