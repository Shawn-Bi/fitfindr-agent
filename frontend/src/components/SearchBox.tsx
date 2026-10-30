"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { SearchIcon } from "./Icons";
import { PhotoSearchButton } from "./ComingSoon";

/** Free-text search. Submitting goes to /search?q=… (P5). */
export function SearchBox({
  initial = "",
  placeholder = "vintage white shirt under $30",
  variant = "phone",
  label = "Search secondhand",
  autoFocus = false,
  extraQuery = "",
}: {
  initial?: string;
  placeholder?: string;
  variant?: "phone" | "desktop" | "landing";
  label?: string;
  autoFocus?: boolean;
  /** Filter params (B4) to carry into the search, e.g. "min=10&max=40". */
  extraQuery?: string;
}) {
  const router = useRouter();
  const id = useId();
  const [q, setQ] = useState(initial);
  useEffect(() => setQ(initial), [initial]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = q.trim() || placeholder;
    router.push(`/search?q=${encodeURIComponent(text)}${extraQuery ? `&${extraQuery}` : ""}`);
  }

  const desktop = variant === "desktop";
  return (
    <form
      role="search"
      onSubmit={submit}
      className={
        desktop
          ? "flex h-[46px] min-w-0 flex-1 items-center gap-2 rounded-xl border-[1.5px] border-ink bg-bg pl-3.5 pr-1"
          : "flex min-w-0 flex-1 items-center gap-1.5 rounded-2xl border-[1.5px] border-ink bg-surface pl-3 pr-1 " +
            (variant === "landing" ? "h-14 py-1.5" : "h-[50px]")
      }
    >
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <input
        id={id}
        type="search"
        enterKeyHint="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={placeholder}
        autoFocus={autoFocus}
        maxLength={200}
        className="h-full min-w-0 flex-1 border-0 bg-transparent text-[15px] text-ink outline-none placeholder:text-muted [&::-webkit-search-cancel-button]:hidden"
      />
      {desktop && <PhotoSearchButton compact />}
      <button
        type="submit"
        aria-label="Search"
        className={`flex shrink-0 items-center justify-center bg-ink text-white hover:bg-primary-hover ${
          desktop ? "h-[38px] w-[38px] rounded-[9px]" : "h-11 w-11 rounded-[10px]"
        }`}
      >
        <SearchIcon size={desktop ? 18 : 20} />
      </button>
    </form>
  );
}
