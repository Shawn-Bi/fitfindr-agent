import Link from "next/link";

/** The tilted price tag with "FF" (public/logo.svg), drawn inline so it scales crisply. */
export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <g transform="rotate(-8 32 32)">
        <path d="M3 32 L17 11 H56 a6 6 0 0 1 6 6 V47 a6 6 0 0 1 -6 6 H17 Z" fill="#0369A1" />
        <circle cx="14" cy="32" r="3.6" fill="#FFFFFF" />
        <path d="M26 21 V43 M26 21 H36 M26 31.5 H34" stroke="#FFFFFF" strokeWidth="4.6" strokeLinecap="round" fill="none" />
        <path d="M42 21 V43 M42 21 H52 M42 31.5 H50" stroke="#7DD3FC" strokeWidth="4.6" strokeLinecap="round" fill="none" />
      </g>
    </svg>
  );
}

export function Logo({ href = "/", size = 32, wordmark = true }: { href?: string; size?: number; wordmark?: boolean }) {
  return (
    <Link
      href={href}
      aria-label="FitFindr home"
      className="flex min-h-11 shrink-0 items-center gap-1.5 font-heading text-[22px] font-bold tracking-[-0.5px] text-ink no-underline hover:text-ink"
    >
      <LogoMark size={size} />
      {wordmark && (
        <span>
          Fit<span className="text-accent">Findr</span>
        </span>
      )}
    </Link>
  );
}
