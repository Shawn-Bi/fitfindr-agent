"use client";

import { useState } from "react";
import { COLOR_SWATCHES } from "@/lib/format";
import { ShirtIcon } from "./Icons";

export interface CollageTile {
  src: string | null;
  alt: string;
  /** Small badge: "Yours", a store name, or "To find". */
  badge: string;
  kind: "closet" | "find" | "idea";
  /** For "idea" tiles (a planned piece with no listing): what to show instead of a photo. */
  name?: string;
  colors?: string[];
}

function swatchHex(name: string): string | null {
  const n = name.toLowerCase();
  return COLOR_SWATCHES.find((c) => c.name === n || n.includes(c.name))?.hex ?? null;
}

function Tile({ tile, big }: { tile: CollageTile; big: boolean }) {
  const [failed, setFailed] = useState(false);
  const badgeCls =
    tile.kind === "closet" ? "bg-ink text-white" : tile.kind === "find" ? "bg-surface text-ink" : "bg-tint text-primary-hover";
  return (
    <figure className={`relative m-0 flex min-h-0 items-center justify-center overflow-hidden rounded-xl bg-white ${big ? "row-span-2" : ""}`}>
      {tile.kind === "idea" || !tile.src || failed ? (
        <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-bg p-3 text-center">
          {tile.kind === "idea" ? (
            <>
              <div className="flex gap-1" aria-hidden="true">
                {(tile.colors || []).slice(0, 3).map((c) => (
                  <span
                    key={c}
                    className="h-4 w-4 rounded-full border border-line"
                    style={{ background: swatchHex(c) || "#DCEFFB" }}
                  />
                ))}
              </div>
              <span className="line-clamp-3 text-xs font-bold leading-tight text-ink md:text-[13px]">{tile.name}</span>
            </>
          ) : (
            <span className="text-muted">
              <ShirtIcon />
            </span>
          )}
          <span className="sr-only">{tile.alt}</span>
        </div>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element -- signed Supabase URLs and store images from many hosts
        <img
          src={tile.src}
          alt={tile.alt}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className="h-full w-full object-contain p-1.5"
        />
      )}
      <figcaption className={`absolute bottom-1.5 left-1.5 rounded-full px-2 py-0.5 text-[11px] font-bold ${badgeCls}`}>
        {tile.badge}
      </figcaption>
    </figure>
  );
}

/**
 * An outfit as one picture (A5): the user's own piece(s) and the finds, on a
 * clean white board. 1–2 tiles side by side; 3 tiles = one large + two; 4 = a 2×2 grid.
 */
export function OutfitCollage({ tiles, label, className = "" }: { tiles: CollageTile[]; label: string; className?: string }) {
  const shown = tiles.slice(0, 4);
  if (shown.length === 0) return null;
  const layout =
    shown.length === 1
      ? "grid-cols-1 grid-rows-1"
      : shown.length === 2
        ? "grid-cols-2 grid-rows-1"
        : "grid-cols-2 grid-rows-2";
  return (
    <div
      role="group"
      aria-label={label}
      className={`grid aspect-[4/3] w-full gap-1.5 rounded-2xl border border-line-blue bg-white p-1.5 ${layout} ${className}`}
    >
      {shown.map((t, i) => (
        <Tile key={`${t.badge}-${i}`} tile={t} big={shown.length === 3 && i === 0} />
      ))}
    </div>
  );
}
