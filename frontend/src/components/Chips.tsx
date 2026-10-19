"use client";

/** A pressable chip (multi- or single-select). 44 px tall for touch. */
export function ToggleChip({
  pressed,
  onClick,
  children,
  disabled = false,
  size = "md",
}: {
  pressed: boolean;
  onClick: () => void;
  children: React.ReactNode;
  disabled?: boolean;
  size?: "md" | "sm";
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      disabled={disabled}
      className={`${size === "sm" ? "h-11 min-w-11 px-2.5 text-[13px]" : "h-11 px-3.5 text-sm"} rounded-full border-[1.5px] ${
        pressed ? "border-ink bg-ink font-bold text-white" : "border-line bg-surface text-ink hover:border-ink"
      } disabled:cursor-not-allowed disabled:border-line-soft disabled:text-muted disabled:hover:border-line-soft`}
    >
      {children}
    </button>
  );
}

/** A round colour swatch with its name for screen readers and on hover. */
export function Swatch({
  name,
  hex,
  selected,
  onClick,
}: {
  name: string;
  hex: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      aria-label={name}
      title={name}
      style={{ background: hex }}
      className={`h-11 w-11 shrink-0 rounded-full ${
        selected ? "border-[3px] border-white shadow-[0_0_0_2px_#0369A1]" : "border-[1.5px] border-line"
      }`}
    />
  );
}

/** The small "AI suggested" badge next to a field the photo filled in (A3). */
/**
 * A compact rounded-rectangle size chip (US retail style). Still 44 px tall
 * for touch; the selected state is the primary blue.
 */
export function SizeChip({
  pressed,
  onClick,
  children,
  label,
}: {
  pressed: boolean;
  onClick: () => void;
  children: React.ReactNode;
  label?: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      aria-label={label}
      onClick={onClick}
      className={`h-11 min-w-11 shrink-0 whitespace-nowrap rounded-lg border px-2 text-[13px] tabular-nums ${
        pressed ? "border-primary bg-primary font-bold text-white" : "border-line bg-surface text-ink hover:border-primary"
      }`}
    >
      {children}
    </button>
  );
}

/**
 * A group of size chips that never takes more than two lines: on a narrow
 * screen a long group scrolls sideways inside itself (not the page).
 */
export function SizeRow({ children, count }: { children: React.ReactNode; count: number }) {
  return count > 7 ? (
    <div className="-mx-1 grid auto-cols-max grid-flow-col grid-rows-2 gap-1.5 overflow-x-auto px-1 pb-1 md:flex md:flex-wrap md:overflow-visible">
      {children}
    </div>
  ) : (
    <div className="flex flex-wrap gap-1.5">{children}</div>
  );
}

export function AiBadge() {
  return (
    <span className="ml-1.5 inline-flex items-center rounded-full bg-tint px-2 py-0.5 align-middle text-[11px] font-bold text-primary-hover">
      AI suggested
    </span>
  );
}

export function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}
