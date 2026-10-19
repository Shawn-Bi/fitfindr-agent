"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { BackIcon } from "@/components/Icons";

type Table = { title: string; note?: string; head: string[]; rows: string[][] };

// Approximate US retail sizing (body measurements in inches). Brands vary;
// the listing's own measurements always win.
const WOMEN: Table[] = [
  {
    title: "Tops & dresses",
    head: ["Size", "Numeric", "Bust", "Waist", "Hip"],
    rows: [
      ["XXS", "00", "31–32", "23–24", "33–34"],
      ["XS", "0–2", "32–33", "24–25", "34–35"],
      ["S", "4–6", "34–35", "26–27", "36–37"],
      ["M", "8–10", "36–37", "28–29", "38–39"],
      ["L", "12–14", "38½–40", "30½–32", "40½–42"],
      ["XL", "16", "41½–43", "33½–35", "43½–45"],
      ["XXL", "18–20", "44–46", "36–38", "46–48"],
    ],
  },
  {
    title: "Plus",
    head: ["Size", "Numeric", "Bust", "Waist", "Hip"],
    rows: [
      ["1X", "14W–16W", "42–44", "35–37", "45–47"],
      ["2X", "18W–20W", "45–47", "38–40", "48–50"],
      ["3X", "22W–24W", "48–50", "41–43", "51–53"],
      ["4X", "26W–28W", "51–53", "44–46", "54–56"],
    ],
  },
  {
    title: "Jeans (waist)",
    note: "Petite is cut for 5′4″ and under; pick Petite above and your usual size.",
    head: ["Waist", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32"],
    rows: [["Numeric", "00", "00", "0", "2", "4", "6", "8", "10", "12", "14"]],
  },
  {
    title: "Pants inseam",
    head: ["Short", "Regular", "Long"],
    rows: [["28–29 in", "30–32 in", "33–34 in"]],
  },
];

const MEN: Table[] = [
  {
    title: "Tops",
    head: ["Size", "Chest", "Neck"],
    rows: [
      ["S", "35–37", "14–14½"],
      ["M", "38–40", "15–15½"],
      ["L", "41–43", "16–16½"],
      ["XL", "44–46", "17–17½"],
      ["XXL", "47–49", "18–18½"],
    ],
  },
  {
    title: "Dress shirts",
    note: "Neck: around the base of the neck. Sleeve: from the center back of the neck to the wrist.",
    head: ["Neck", "14–14½", "15–15½", "16–16½", "17–17½", "18"],
    rows: [["Sleeve", "32–33", "32–34", "33–35", "34–36", "35–36"]],
  },
  {
    title: "Pants",
    note: "Pants are sold as waist × inseam, e.g. 32×30.",
    head: ["Waist", "28–30", "31–33", "34–36", "38–40", "42–44"],
    rows: [["Letter", "S", "M", "L", "XL", "XXL"]],
  },
];

const SHOES: Table = {
  title: "Shoes",
  note: "A US women's size is about 1½ sizes above the same US men's size.",
  head: ["Women's", "6", "7", "8", "9", "10", "11", "12"],
  rows: [["Men's", "4½", "5½", "6½", "7½", "8½", "9½", "10½"]],
};

function SizeTable({ t }: { t: Table }) {
  return (
    <section className="flex min-w-0 flex-col gap-2 rounded-2xl bg-surface p-4">
      <h3 className="m-0 text-[15px] font-bold">{t.title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-[13px] tabular-nums">
          <thead>
            <tr>
              {t.head.map((h) => (
                <th key={h} scope="col" className="whitespace-nowrap border-b border-line-soft px-2 py-1.5 font-bold">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {t.rows.map((r) => (
              <tr key={r.join("|")}>
                {r.map((c, i) => (
                  <td key={i} className={`whitespace-nowrap border-b border-line-soft px-2 py-1.5 ${i === 0 ? "font-bold" : ""}`}>
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {t.note && <p className="m-0 text-xs text-muted">{t.note}</p>}
    </section>
  );
}

/** US size guide linked from the profile's size section (approximate body measurements). */
export default function Page() {
  return (
    <AppShell>
      <div className="mx-auto flex max-w-[1000px] flex-col gap-4 px-4 pb-10 pt-4 md:px-6 md:pt-8">
        <div className="flex items-center gap-1.5">
          <Link href="/profile" aria-label="Back to profile" className="flex h-11 w-11 items-center justify-center text-ink">
            <BackIcon />
          </Link>
          <h1 className="m-0 font-heading text-2xl font-bold">Size guide (US)</h1>
        </div>
        <p className="m-0 text-sm text-muted">
          Body measurements in inches, the way US stores like Nordstrom, Madewell and J.Crew size. Brands vary, and
          secondhand pieces can shrink or stretch — check the measurements in the listing when it has them.
        </p>
        <h2 className="m-0 mt-2 font-heading text-lg font-bold">Women</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {WOMEN.map((t) => (
            <SizeTable key={t.title} t={t} />
          ))}
        </div>
        <h2 className="m-0 mt-2 font-heading text-lg font-bold">Men</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {MEN.map((t) => (
            <SizeTable key={t.title} t={t} />
          ))}
        </div>
        <SizeTable t={SHOES} />
      </div>
    </AppShell>
  );
}
