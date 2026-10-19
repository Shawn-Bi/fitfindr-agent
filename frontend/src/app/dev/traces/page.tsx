"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RequireAuth } from "@/components/RequireAuth";
import { ErrorBox, Spinner } from "@/components/States";
import { api, ApiError } from "@/lib/api";

interface Trace {
  id: string;
  created_at: string;
  kind: string;
  query: string | null;
  planner: string | null;
  outcome: string | null;
  steps: { tool: string; by?: string; ms?: number; args?: unknown; result?: unknown; note?: string }[];
  tool_calls: number;
  model_calls: number;
  latency_ms: number;
  prompt_tokens: number;
  output_tokens: number;
  est_cost_usd: number;
}

function when(iso: string) {
  return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

/** Dev only (A2): the latest agent runs with steps, latency, tokens and estimated cost. */
function Traces() {
  const [rows, setRows] = useState<Trace[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api<{ traces: Trace[] }>("/dev/traces?limit=100")
      .then((d) => setRows(d.traces))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load traces."));
  }, []);
  useEffect(load, [load]);

  const total = rows?.reduce((sum, r) => sum + Number(r.est_cost_usd || 0), 0) ?? 0;

  return (
    <AppShell>
      <div className="mx-auto max-w-[1200px] px-4 pb-8 md:px-6 md:pt-6">
        <header className="flex flex-wrap items-end justify-between gap-2 pb-3 pt-5 md:pt-0">
          <div>
            <h1 className="m-0 font-heading text-[28px] font-bold">Agent traces</h1>
            <p className="m-0 text-sm text-muted">
              Development only — not served in production. Cost is an estimate at paid-tier list prices.
            </p>
          </div>
          <button type="button" onClick={load} className="h-11 rounded-xl border-[1.5px] border-ink bg-surface px-4 font-bold">
            Refresh
          </button>
        </header>
        {error && <ErrorBox message={error} onRetry={load} />}
        {!rows && !error && <Spinner />}
        {rows && (
          <>
            <p className="mt-0 text-sm text-muted">
              {rows.length} runs · estimated ${total.toFixed(4)} total
            </p>
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {rows.map((r) => (
                <li key={r.id} className="rounded-2xl bg-surface p-3">
                  <details>
                    <summary className="flex min-h-11 cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                      <span className="w-[120px] shrink-0 text-muted">{when(r.created_at)}</span>
                      <span className="rounded-full bg-tint px-2 py-0.5 text-xs font-bold text-primary-hover">{r.kind}</span>
                      <span className="min-w-0 flex-1 truncate font-bold">{r.query || "—"}</span>
                      <span className="text-xs text-muted">
                        {r.outcome} · {r.planner || "—"} · {r.tool_calls} tools · {r.model_calls} model calls ·{" "}
                        {(r.latency_ms / 1000).toFixed(1)} s · {r.prompt_tokens + r.output_tokens} tokens · $
                        {Number(r.est_cost_usd).toFixed(5)}
                      </span>
                    </summary>
                    <ol className="mb-0 mt-2 flex flex-col gap-1.5 pl-5 text-[13px]">
                      {r.steps.map((s, i) => (
                        <li key={i}>
                          <strong>{s.tool}</strong>
                          {s.by && <span className="text-muted"> · {s.by}</span>}
                          {s.ms != null && <span className="text-muted"> · {s.ms} ms</span>}
                          {s.note && <span className="text-muted"> · {s.note}</span>}
                          <pre className="m-0 mt-0.5 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-bg p-2 text-xs">
                            {JSON.stringify({ args: s.args, result: s.result }, null, 1)}
                          </pre>
                        </li>
                      ))}
                    </ol>
                  </details>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </AppShell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Traces />
    </RequireAuth>
  );
}
