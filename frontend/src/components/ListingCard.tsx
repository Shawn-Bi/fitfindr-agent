"use client";

import Link from "next/link";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { cleanTitle, listingMeta, money, STORE_LABELS } from "@/lib/format";
import type { Listing } from "@/lib/types";
import { useAuth } from "./AuthProvider";
import { HeartIcon, ShirtIcon } from "./Icons";

export function ListingImage({ listing, className = "" }: { listing: Listing; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (!listing.image_url || failed) {
    return (
      <div className={`flex items-center justify-center bg-line-soft text-muted ${className}`}>
        <ShirtIcon />
        <span className="sr-only">No photo available</span>
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- store images come from many hosts
    <img
      src={listing.image_url}
      alt={cleanTitle(listing.title)}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={`object-cover ${className}`}
    />
  );
}

/** Heart toggle. Guests are sent to sign up instead. */
export function SaveButton({
  listing,
  saved: initial = false,
  variant = "overlay",
  onChange,
}: {
  listing: Listing;
  saved?: boolean;
  variant?: "overlay" | "outline";
  onChange?: (saved: boolean) => void;
}) {
  const { session } = useAuth();
  const [saved, setSaved] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const title = cleanTitle(listing.title);
  const cls =
    variant === "overlay"
      ? "flex h-11 w-11 items-center justify-center rounded-full bg-surface/90 text-ink shadow-sm hover:bg-surface"
      : "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border-[1.5px] border-line-dash bg-surface text-ink hover:bg-tint";

  if (!session) {
    return (
      <Link href="/signup" aria-label={`Sign up to save ${title}`} className={`${cls} no-underline`}>
        <HeartIcon />
      </Link>
    );
  }

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      if (saved) {
        await api(`/saved/${listing.platform}/${encodeURIComponent(listing.id)}`, { method: "DELETE" });
      } else {
        const { saved: _ignored, ...plain } = listing;
        void _ignored;
        await api("/saved", { json: { listing: plain } });
      }
      setSaved(!saved);
      onChange?.(!saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        aria-pressed={saved}
        aria-label={saved ? `Remove ${title} from Saved` : `Save ${title}`}
        className={`${cls} ${saved ? "text-primary" : ""} disabled:opacity-60`}
      >
        <HeartIcon filled={saved} />
      </button>
      {error && (
        <span role="alert" className="sr-only">
          {error}
        </span>
      )}
    </>
  );
}

/** Grid card: photo, title, meta, price, store link, heart. */
export function ListingCard({
  listing,
  reason,
  imageHeight = "h-[150px] md:h-[170px]",
}: {
  listing: Listing;
  reason?: string | null;
  imageHeight?: string;
}) {
  const title = cleanTitle(listing.title);
  return (
    <article className="relative flex flex-col overflow-hidden rounded-2xl bg-surface">
      <a
        href={listing.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex flex-1 flex-col text-ink no-underline hover:text-ink"
      >
        <ListingImage listing={listing} className={`${imageHeight} w-full`} />
        <div className="flex flex-col gap-[3px] px-3 pb-3 pt-2.5">
          <h3 className="m-0 line-clamp-2 text-sm font-bold leading-tight">{title}</h3>
          <div className="text-[13px] text-muted">{listingMeta(listing)}</div>
          <div className="text-base font-bold">{money(listing.price)}</div>
          {reason && <div className="text-xs text-primary">{reason}</div>}
          <span className="sr-only">Opens on {STORE_LABELS[listing.platform]} in a new tab</span>
        </div>
      </a>
      <div className="absolute right-1 top-1">
        <SaveButton listing={listing} saved={listing.saved} />
      </div>
    </article>
  );
}
