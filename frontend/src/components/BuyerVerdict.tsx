"use client";

import { useState } from "react";
import { money } from "@/lib/format";
import type { FitVerdict } from "@/lib/types";

export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        } catch {
          setCopied(false);
        }
      }}
      className="h-11 shrink-0 rounded-[10px] border-[1.5px] border-ink bg-surface px-3 text-[13px] font-bold hover:bg-tint"
    >
      <span aria-live="polite">{copied ? "Copied" : "Copy caption"}</span>
    </button>
  );
}

const VERDICT_STYLE: Record<string, string> = {
  "Worth it": "bg-success text-white",
  "Fair deal": "bg-primary text-white",
  Skip: "bg-danger text-white",
};

function Estimate({ confidence }: { confidence: string }) {
  return (
    <span className="ml-1 whitespace-nowrap rounded-full bg-tint px-1.5 py-0.5 text-[11px] font-bold text-primary-hover">
      AI estimate · {confidence} confidence
    </span>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-line-soft py-2 text-[13px] last:border-0 sm:flex-row sm:gap-3 md:text-sm">
      <dt className="w-28 shrink-0 text-muted">{label}</dt>
      <dd className="m-0 min-w-0">{children}</dd>
    </div>
  );
}

/**
 * The fit card as a short buyer's verdict (B1): AI estimates of original
 * retail and era (labelled, with confidence, or "Unknown"), value, a condition
 * check from what the store states, Worth it / Fair deal / Skip with reasons,
 * and the shareable caption with Copy.
 */
export function BuyerVerdict({ verdict, caption, price }: { verdict: FitVerdict | null; caption: string; price: number }) {
  const v = verdict;
  return (
    <section
      aria-labelledby="verdict-title"
      className="flex flex-col gap-2.5 rounded-[14px] border-[1.5px] border-dashed border-line-dash p-3 md:px-3.5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="verdict-title" className="m-0 text-[13px] font-bold md:text-sm">
          Fit card · buyer&apos;s verdict
        </h3>
        {v?.verdict && (
          <span className={`rounded-full px-3 py-1 text-[13px] font-bold ${VERDICT_STYLE[v.verdict]}`}>{v.verdict}</span>
        )}
      </div>

      {v && v.reasons.length > 0 && (
        <ul className="m-0 flex list-disc flex-col gap-0.5 pl-5 text-[13px] md:text-sm">
          {v.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}

      {v && (
        <dl className="m-0 rounded-xl bg-bg px-3 py-0.5">
          <Row label="Original retail">
            {v.retail ? (
              <>
                {money(v.retail.low)}
                {v.retail.high !== v.retail.low && `–${money(v.retail.high)}`}
                <Estimate confidence={v.retail.confidence} />
                <div className="text-muted">
                  {v.retail.pct_off != null
                    ? `This price (${money(price)}) is about ${v.retail.pct_off}% below that estimate.`
                    : v.retail.above_retail
                      ? `This price (${money(price)}) is above that estimate.`
                      : null}
                </div>
              </>
            ) : (
              <span>Unknown — not enough to estimate confidently.</span>
            )}
          </Row>
          <Row label="Era">
            {v.era ? (
              <>
                {v.era.label}
                <Estimate confidence={v.era.confidence} />
              </>
            ) : (
              "Unknown"
            )}
          </Row>
          <Row label="Value">
            {v.longevity && (
              <span className="mr-1.5 rounded-full border border-line px-2 py-0.5 text-[11px] font-bold">
                {v.longevity === "classic" ? "Classic" : v.longevity === "trend-driven" ? "Trend-driven" : "Classic + trend"}
              </span>
            )}
            {v.brand_value || "No brand or resale signal to go on."}
          </Row>
          <Row label="Condition">
            {v.condition.label || v.condition.stated ? (
              <>
                <strong>{v.condition.label || v.condition.stated}</strong> (as the seller states)
                {v.condition.notes && <div className="text-muted">{v.condition.notes}</div>}
              </>
            ) : (
              <>Not stated by the seller — ask before buying.</>
            )}
          </Row>
        </dl>
      )}

      <div className="flex flex-col gap-2 rounded-xl bg-surface md:flex-row md:items-start md:gap-3">
        <p className="m-0 flex-1 text-[13px] leading-[1.45] text-ink-soft md:text-sm md:leading-normal">
          <strong>Caption: </strong>
          {caption}
        </p>
        <CopyButton text={caption} />
      </div>
      {v && (
        <p className="m-0 text-[11px] text-muted md:text-xs">
          Estimates are AI guesses from the listing title, not facts. Check the original listing.
        </p>
      )}
    </section>
  );
}
