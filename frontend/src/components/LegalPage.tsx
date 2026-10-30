import { readFile } from "node:fs/promises";
import path from "node:path";
import Link from "next/link";
import { Markdown } from "@/lib/markdown";
import { Logo } from "./Logo";

/** Renders docs/legal/<name>.md at build time with a DRAFT banner (DECISIONS.md #29). */
export async function LegalPage({ file }: { file: "terms.md" | "privacy.md" }) {
  const source = await readFile(path.join(process.cwd(), "..", "docs", "legal", file), "utf-8");
  // The file's own first line is a draft note; the banner below replaces it.
  const body = source.replace(/^DRAFT[^\n]*\n/, "");
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex max-w-[800px] items-center justify-between px-5 py-4">
        <Logo />
        <nav aria-label="Legal" className="flex gap-3 text-sm">
          <Link href="/terms" className="flex h-11 items-center">
            Terms
          </Link>
          <Link href="/privacy" className="flex h-11 items-center">
            Privacy
          </Link>
        </nav>
      </header>
      <main id="main" className="mx-auto max-w-[800px] px-5 pb-16">
        <div role="note" className="rounded-xl border-[1.5px] border-dashed border-ink bg-[#FFF6D6] p-3 text-sm font-bold">
          DRAFT — not yet reviewed by a lawyer. Bracketed placeholders will be filled in before launch.
        </div>
        <article className="text-[15px] text-ink">
          <Markdown source={body} />
        </article>
      </main>
    </div>
  );
}
