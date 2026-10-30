"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { cleanTitle, COLOR_SWATCHES, money, STORE_LABELS, timeAgo } from "@/lib/format";
import type { ClosetItem, OutfitPiece, OutfitResponse } from "@/lib/types";
import { ExternalIcon, SearchIcon, ShirtIcon } from "./Icons";
import { SaveButton } from "./ListingCard";
import { ErrorBox, Spinner } from "./States";

const POLL_MS = 3000;
const POLL_LIMIT = 60; // ~3 minutes

function hexFor(name: string) {
  const n = name.toLowerCase();
  return COLOR_SWATCHES.find((c) => c.name === n || n.includes(c.name))?.hex ?? "#DCEFFB";
}

const BADGES: Record<string, { text: string; cls: string }> = {
  listing: { text: "Real listing", cls: "bg-surface text-ink" },
  closest: { text: "Closest find", cls: "bg-[#FFF6D6] text-ink" },
  ai_preview: { text: "AI preview — not a real listing", cls: "bg-tint text-primary-hover" },
  idea: { text: "To find", cls: "bg-tint text-primary-hover" },
};

function Picture({ src, alt }: { src: string | null | undefined; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed)
    return (
      <div className="flex h-full w-full items-center justify-center bg-bg text-muted">
        <ShirtIcon />
        <span className="sr-only">{alt}</span>
      </div>
    );
  return (
    // eslint-disable-next-line @next/next/no-img-element -- signed Supabase URLs and store images from many hosts
    <img src={src} alt={alt} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)}
      className="h-full w-full object-contain p-1.5" />
  );
}

/** One planned piece: its picture, name, why it works, and either the listing (price, store, View on …) or Search this. */
function PieceCard({ piece }: { piece: OutfitPiece }) {
  const kind = piece.kind || (piece.listing ? "listing" : "idea");
  const l = kind === "listing" || kind === "closest" ? piece.listing : null;
  const badge = BADGES[kind];
  const store = l ? STORE_LABELS[l.platform] : null;
  return (
    <li className="flex min-w-0 flex-col overflow-hidden rounded-2xl bg-surface">
      <div className="relative aspect-[4/5] w-full bg-white">
        {kind === "idea" ? (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-bg p-3 text-center" aria-hidden="true">
            <div className="flex gap-1">
              {piece.colors.slice(0, 3).map((c) => (
                <span key={c} className="h-5 w-5 rounded-full border border-line" style={{ background: hexFor(c) }} />
              ))}
            </div>
            <span className="line-clamp-3 text-xs font-bold leading-tight text-ink">{piece.name}</span>
          </div>
        ) : l ? (
          <a href={l.url} target="_blank" rel="noopener noreferrer" className="block h-full w-full" tabIndex={-1} aria-hidden="true">
            <Picture src={l.image_url} alt={cleanTitle(l.title)} />
          </a>
        ) : (
          <Picture src={piece.preview_url} alt={`AI preview of ${piece.name}`} />
        )}
        <span className={`absolute bottom-1.5 left-1.5 right-1.5 w-fit max-w-[calc(100%-12px)] rounded-full px-2 py-0.5 text-[11px] font-bold leading-tight ${badge.cls}`}>
          {kind === "listing" && store ? store : badge.text}
        </span>
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 p-2.5 md:p-3">
        <div className="text-[11px] font-bold uppercase tracking-wide text-primary">{piece.label}</div>
        <h3 className="m-0 text-sm font-bold leading-tight md:text-[15px]">{piece.name}</h3>
        {piece.why && <p className="m-0 line-clamp-3 text-xs leading-snug text-muted md:text-[13px]">{piece.why}</p>}
        {l ? (
          <div className="mt-auto flex flex-col gap-1.5 pt-1.5">
            <div className="flex flex-wrap items-baseline gap-x-1.5 text-[13px]">
              <span className="font-bold">{money(l.price)}</span>
              <span className="text-muted">· {store}</span>
            </div>
            <p className="m-0 line-clamp-2 text-[11px] text-muted">
              {kind === "closest" ? `${piece.closest_note || "Closest real listing"}: ` : ""}
              {cleanTitle(l.title)}
              {piece.found_at && ` · found ${timeAgo(piece.found_at)}`}
            </p>
            <div className="flex items-center gap-1.5">
              <a
                href={l.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex min-h-11 min-w-0 flex-1 items-center justify-center gap-1 rounded-xl bg-primary px-2 text-center text-[13px] font-bold leading-tight text-white no-underline hover:bg-primary-hover hover:text-white"
              >
                View on {store} <ExternalIcon />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
              <SaveButton listing={l} saved={l.saved} variant="outline" />
            </div>
          </div>
        ) : (
          <div className="mt-auto flex flex-col items-start gap-1.5 pt-1.5">
            {piece.expired && <span className="text-[11px] text-muted">The find we had is over 24 hours old.</span>}
            <Link
              href={`/search?q=${encodeURIComponent(piece.search)}`}
              className="flex min-h-11 w-full items-center justify-center gap-1.5 rounded-xl border-[1.5px] border-ink bg-surface px-2 text-[13px] font-bold text-ink no-underline hover:bg-tint hover:text-ink"
            >
              <SearchIcon size={16} /> Search this
            </Link>
          </div>
        )}
      </div>
    </li>
  );
}

/**
 * P8 "Finds that go with this" (B2): the AI stylist's complete outfit built
 * for this closet item, as one set of cards: your piece, then each planned
 * piece with its picture — a real listing, the "Closest find", or an "AI
 * preview" — and either View on … or Search this. Never an empty tile.
 */
export function StylistOutfit({ item }: { item: ClosetItem }) {
  const [data, setData] = useState<OutfitResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [restyling, setRestyling] = useState(false);
  const polls = useRef(0);

  const load = useCallback(() => {
    api<OutfitResponse>(`/closet/items/${item.id}/outfit`)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load the outfit."));
  }, [item.id]);

  useEffect(load, [load]);

  // While the stylist works (after an add or edit), check back every few seconds.
  useEffect(() => {
    if (data?.status !== "pending" || polls.current >= POLL_LIMIT) return;
    const t = setTimeout(() => {
      polls.current += 1;
      load();
    }, POLL_MS);
    return () => clearTimeout(t);
  }, [data, load]);

  async function restyle() {
    setRestyling(true);
    try {
      await api(`/closet/items/${item.id}/outfit`, { method: "POST" });
      polls.current = 0;
      setData((d) => ({ ...(d || { outfit: null, stale: false, item_photo: null }), status: "pending" }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't restyle right now.");
    } finally {
      setRestyling(false);
    }
  }

  const o = data?.outfit;
  const yours = data?.item_photo || item.photo;

  return (
    <section aria-labelledby="finds-title" className="flex flex-col gap-3 pb-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="finds-title" className="m-0 mt-2 font-heading text-lg font-bold">
          Finds that go with this
        </h2>
        {data?.status === "ready" && (
          <button
            type="button"
            onClick={restyle}
            disabled={restyling}
            className="flex h-11 items-center rounded-xl px-3 text-sm font-bold text-primary hover:bg-tint disabled:opacity-60"
          >
            Restyle
          </button>
        )}
      </div>

      {error && <ErrorBox message={error} onRetry={load} />}
      {!data && !error && <Spinner label="Loading your outfit" />}

      {data?.status === "pending" && (
        <div role="status" className="flex flex-col gap-1 rounded-2xl bg-surface p-4">
          <Spinner label="Styling your piece" />
          <p className="m-0 text-sm text-muted">
            FitFindr is planning an outfit around your {item.name.toLowerCase()} and checking real listings. This
            usually takes under a minute.
          </p>
        </div>
      )}

      {data?.status === "none" && (
        <div className="flex flex-col items-start gap-2 rounded-2xl bg-surface p-4">
          <p className="m-0 text-sm text-muted">No outfit for this piece yet.</p>
          <button
            type="button"
            onClick={restyle}
            disabled={restyling}
            className="h-11 rounded-xl bg-primary px-4 font-bold text-white hover:bg-primary-hover disabled:opacity-60"
          >
            Style this piece
          </button>
        </div>
      )}

      {data?.status === "failed" && (
        <ErrorBox message="The stylist couldn't finish this outfit. Your closet is fine." onRetry={restyle} />
      )}

      {data?.status === "ready" && o && (
        <article className="flex flex-col gap-3" aria-label={`Outfit: ${o.title}`}>
          <div className="flex flex-col gap-1.5 rounded-2xl bg-surface p-4">
            <div className="text-[11px] font-bold uppercase tracking-wide text-primary">Styled for you</div>
            <h3 className="m-0 font-heading text-xl font-bold leading-tight">{o.title}</h3>
            {o.concept && <p className="m-0 text-sm leading-relaxed">{o.concept}</p>}
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
              {o.palette.length > 0 && (
                <span className="flex items-center gap-1" aria-label={`Palette: ${o.palette.join(", ")}`}>
                  {o.palette.map((c) => (
                    <span key={c} title={c} className="h-5 w-5 rounded-full border border-line" style={{ background: hexFor(c) }} />
                  ))}
                </span>
              )}
              {o.occasion && <span className="rounded-full bg-bg px-2.5 py-1">{o.occasion}</span>}
              {o.styles.map((s) => (
                <span key={s} className="rounded-full bg-tint px-2.5 py-1 font-bold text-primary-hover">
                  {s}
                </span>
              ))}
            </div>
            {o.default_style && (
              <p className="m-0 text-xs text-muted">
                No styles in your profile yet, so this uses an elevated quiet-luxury look.{" "}
                <Link href="/profile">Choose styles</Link>
              </p>
            )}
            {data.stale && <p className="m-0 text-xs text-muted">You edited this piece; restyle to update the outfit.</p>}
          </div>

          <ul className="m-0 grid list-none grid-cols-2 gap-2.5 p-0 md:grid-cols-4" aria-label={`Your ${item.name} with ${o.pieces.map((p) => p.name).join(", ")}`}>
            <li className="flex min-w-0 flex-col overflow-hidden rounded-2xl bg-surface">
              <div className="relative aspect-[4/5] w-full bg-white">
                <Picture src={yours} alt={`Your ${item.name}`} />
                <span className="absolute bottom-1.5 left-1.5 rounded-full bg-ink px-2 py-0.5 text-[11px] font-bold text-white">Yours</span>
              </div>
              <div className="flex flex-col gap-1 p-2.5 md:p-3">
                <div className="text-[11px] font-bold uppercase tracking-wide text-primary">Your piece</div>
                <h3 className="m-0 text-sm font-bold leading-tight md:text-[15px]">{item.name}</h3>
              </div>
            </li>
            {o.pieces.map((p) => (
              <PieceCard key={p.slot} piece={p} />
            ))}
          </ul>

          {(o.notes.colour || o.notes.proportion || o.notes.fabric) && (
            <dl className="m-0 grid gap-2 rounded-2xl bg-surface p-4 text-[13px] md:grid-cols-3">
              {(
                [
                  ["Colour", o.notes.colour],
                  ["Proportion", o.notes.proportion],
                  ["Fabric", o.notes.fabric],
                ] as const
              ).map(([k, v]) =>
                v ? (
                  <div key={k}>
                    <dt className="font-bold">{k}</dt>
                    <dd className="m-0 text-muted">{v}</dd>
                  </div>
                ) : null,
              )}
            </dl>
          )}

          <p className="m-0 text-xs text-muted">
            Real listings and closest finds are secondhand pieces from the stores; price and stock may change on
            the original site. AI previews only show the idea.
            {o.data_mode === "fixtures" && " Development mode: recorded responses, not a live search."}
          </p>
        </article>
      )}
    </section>
  );
}
