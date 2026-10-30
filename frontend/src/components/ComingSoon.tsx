"use client";

import { useEffect, useRef, useState } from "react";
import { CameraIcon } from "./Icons";

/** A small modal that says a feature isn't built yet (DECISIONS.md #28). */
export function ComingSoonDialog({ open, onClose, title, children }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-4 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="coming-soon-title"
        className="w-full max-w-sm rounded-2xl bg-surface p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="inline-block rounded-full bg-tint px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-primary">
          Coming soon
        </span>
        <h2 id="coming-soon-title" className="mt-3 font-heading text-xl font-bold">
          {title}
        </h2>
        <div className="mt-2 text-[15px] leading-relaxed text-muted">{children}</div>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          className="mt-5 h-12 w-full rounded-xl bg-primary font-bold text-white hover:bg-primary-hover"
        >
          Got it
        </button>
      </div>
    </div>
  );
}

export function PhotoSearchButton({ compact = false }: { compact?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        aria-label="Search by photo — coming soon"
        onClick={() => setOpen(true)}
        className={
          compact
            ? "relative flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-ink hover:bg-tint"
            : "relative flex h-[50px] w-[50px] shrink-0 items-center justify-center rounded-2xl border-[1.5px] border-line bg-surface text-ink hover:bg-tint"
        }
      >
        <CameraIcon />
        {!compact && (
          <span className="absolute -right-1.5 -top-2 rounded-full bg-tint px-1.5 py-0.5 text-[9px] font-bold text-primary">
            SOON
          </span>
        )}
      </button>
      <ComingSoonDialog open={open} onClose={() => setOpen(false)} title="Search by photo">
        Soon you&apos;ll be able to upload a photo and find similar secondhand pieces. For now,
        describe what you want in plain words, like &ldquo;vintage graphic tee under $30&rdquo;.
      </ComingSoonDialog>
    </>
  );
}
