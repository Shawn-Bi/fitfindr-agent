export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-3 text-muted">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-line border-t-primary" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-2xl border border-danger/30 bg-surface p-4 text-[15px]">
      <p className="m-0 text-danger">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 h-11 rounded-xl border-[1.5px] border-ink bg-surface px-4 font-bold hover:bg-tint"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function SkeletonGrid({ count = 4, className = "" }: { count?: number; className?: string }) {
  return (
    <div className={`grid grid-cols-2 gap-3 ${className}`} aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="overflow-hidden rounded-2xl bg-surface">
          <div className="h-[150px] animate-pulse bg-line-soft" />
          <div className="space-y-2 p-3">
            <div className="h-3 w-3/4 animate-pulse rounded bg-line-soft" />
            <div className="h-3 w-1/2 animate-pulse rounded bg-line-soft" />
          </div>
        </div>
      ))}
    </div>
  );
}
