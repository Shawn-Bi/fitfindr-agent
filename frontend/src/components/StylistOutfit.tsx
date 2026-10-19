"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { cleanTitle, COLOR_SWATCHES, money, STORE_LABELS, timeAgo } from "@/lib/format";
import type { ClosetItem, OutfitPiece, OutfitResponse } from "@/lib/types";
import { ExternalIcon, SearchIcon } from "./Icons";
import { ListingImage, SaveButton } from "./ListingCard";
import { OutfitCollage, type CollageTile } from "./OutfitCollage";
import { ErrorBox, Spinner } from "./States";

const POLL_MS = 3000;
const POLL_LIMIT = 60; // ~3 minutes

function hexFor(name: string) {
  const n = name.toLowerCase();
  return COLOR_SWATCHES.find((c) => c.name === n || n.includes(c.name))?.hex ?? "#DCEFFB";
}

function Piece({ piece }: { piece: OutfitPiece }) {
  const l = piece.listing;
  return (
    <li className="flex min-w-0 gap-3 rounded-2xl bg-surface p-3">
      {l ? (
        <a href={l.url} target="_blank" rel="noopener noreferrer" className="shrink-0" aria-label={`${cleanTitle(l.title)} on ${STORE_LABELS[l.platform]} (opens in a new tab)`}>
          <ListingImage listing={l} className="h-[104px] w-[84px] rounded-xl md:h-[120px] md:w-[96px]" />
        </a>
      ) : (
        <div className="flex h-[104px] w-[84px] shrink-0 flex-col items-center justify-center gap-1.5 rounded-xl bg-bg md:h-[120px] md:w-[96px]" aria-hidden="true">
          <div className="flex gap-1">
            {piece.colors.slice(0, 3).map((c) => (
              <span key={c} className="h-4 w-4 rounded-full border border-line" style={{ background: hexFor(c) }} />
            ))}
          </div>
          <span className="text-[11px] font-bold text-muted">To find</span>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="text-[11px] font-bold uppercase tracking-wide text-primary">{piece.label}</div>
        <h3 className="m-0 text-[15px] font-bold leading-tight">{piece.name}</h3>
        {piece.why && <p className="m-0 text-[13px] leading-snug text-muted">{piece.why}</p>}
        {l ? (
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
            <span className="font-bold">{money(l.price)}</span>
            <span className="text-muted">
              {[l.size, l.condition, STORE_LABELS[l.platform]].filter(Boolean).join(" · ")}
            </span>
            {piece.match_reason && <span className="w-full text-xs text-primary">{piece.match_reason}</span>}
            <span className="w-full text-xs text-muted">
              {cleanTitle(l.title)}
              {piece.found_at && ` · found ${timeAgo(piece.found_at)}`}
            </span>
            <div className="mt-1 flex w-full items-center gap-2">
              <a
                href={l.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex h-11 items-center gap-1.5 rounded-xl bg-primary px-3 text-[13px] font-bold text-white no-underline hover:bg-primary-hover hover:text-white"
              >
                View on {STORE_LABELS[l.platform]} <ExternalIcon />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
              <SaveButton listing={l} saved={l.saved} variant="outline" />
            </div>
          </div>
        ) : (
          <div className="mt-1 flex flex-col items-start gap-1.5">
            <span className="text-xs text-muted">
              {piece.expired
                ? "The find we had is over 24 hours old, so it's hidden. Search again for fresh ones."
                : "No secondhand listing fits this exactly right now."}
            </span>
            <Link
              href={`/search?q=${encodeURIComponent(piece.search)}`}
              className="flex h-11 items-center gap-1.5 rounded-xl border-[1.5px] border-ink bg-surface px-3 text-[13px] font-bold text-ink no-underline hover:bg-tint hover:text-ink"
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
 * for this closet item, as a collage (A5) plus each planned piece with a
 * real listing when one truly fits, or a "Search this" button.
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
  const tiles: CollageTile[] = o
    ? [
        { src: data?.item_photo || item.photo, alt: `Your ${item.name}`, badge: "Yours", kind: "closet" },
        ...o.pieces.map(
          (p): CollageTile =>
            p.listing
              ? { src: p.listing.image_url, alt: cleanTitle(p.listing.title), badge: STORE_LABELS[p.listing.platform], kind: "find" }
              : { src: null, alt: `${p.label}: ${p.name} (to find)`, badge: "To find", kind: "idea", name: p.name, colors: p.colors },
        ),
      ]
    : [];

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

          <OutfitCollage tiles={tiles} label={`Outfit collage: your ${item.name} with ${o.pieces.map((p) => p.name).join(", ")}`} />

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

          <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
            {o.pieces.map((p) => (
              <Piece key={p.slot} piece={p} />
            ))}
          </ul>
          <p className="m-0 text-xs text-muted">
            Listings are real secondhand finds; price and stock may change on the original site.
            {o.data_mode === "fixtures" && " Development mode: recorded responses, not a live search."}
          </p>
        </article>
      )}
    </section>
  );
}
