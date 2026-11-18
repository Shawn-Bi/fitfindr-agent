"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import { Logo } from "@/components/Logo";
import { SearchBox } from "@/components/SearchBox";
import { StoreBar } from "@/components/StoreBar";

const STEPS = [
  ["Add your closet", "Snap a photo, add a few details."],
  ["Search in plain words", "Style, size and budget in one line."],
  ["Get matches that go with what you own", "Outfit ideas using your own pieces."],
];

/** P1 Landing — for visitors who aren't signed in. */
export default function Landing() {
  const { session, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading && session) router.replace("/home");
  }, [loading, session, router]);

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="mx-auto flex w-full max-w-[1200px] items-center justify-between gap-3 px-5 py-4 md:px-6">
        <Logo />
        <nav aria-label="Account" className="flex items-center gap-1 text-sm md:gap-3 md:text-base">
          <a href="#how" className="flex h-11 items-center px-2 text-ink no-underline hover:text-primary">
            How it works
          </a>
          <Link href="/login" className="flex h-11 items-center px-2 font-bold text-ink no-underline hover:text-primary">
            Log in
          </Link>
          <Link
            href="/signup"
            className="hidden h-11 items-center rounded-xl bg-primary px-4 font-bold text-white no-underline hover:bg-primary-hover hover:text-white sm:flex"
          >
            Get started
          </Link>
        </nav>
      </header>

      <main id="main" className="mx-auto grid w-full max-w-[1200px] flex-1 gap-8 px-5 pb-6 md:grid-cols-[1.15fr_1fr] md:items-center md:gap-14 md:px-6 md:py-10">
        <section className="flex flex-col gap-3.5 pt-5 md:pt-0">
          <span className="self-start rounded-full bg-tint px-2.5 py-1.5 text-xs font-bold uppercase tracking-[1px] text-primary">
            Secondhand, styled for you
          </span>
          <h1 className="m-0 font-heading text-[38px] font-bold leading-[1.05] tracking-[-1px] md:text-[56px]">
            Find pieces that fit your wardrobe, not just your search.
          </h1>
          <p className="m-0 text-base leading-normal text-muted md:text-lg">
            Secondhand finds from supported stores, matched to your style, size and budget.
          </p>

          <div className="mt-4 flex flex-col gap-2.5 md:max-w-[520px]">
            <span className="text-[13px] font-bold" aria-hidden="true">
              Try a search
            </span>
            <SearchBox variant="landing" placeholder="vintage graphic tee under $30" label="Try a search" />
            <Link
              href="/signup"
              className="flex h-[52px] items-center justify-center rounded-2xl bg-primary text-base font-bold text-white no-underline hover:bg-primary-hover hover:text-white"
            >
              Get started — it&apos;s free
            </Link>
          </div>
        </section>

        <section id="how" className="flex scroll-mt-4 flex-col gap-2.5" aria-labelledby="how-title">
          <h2 id="how-title" className="m-0 font-heading text-lg font-bold md:text-2xl">
            How it works
          </h2>
          {STEPS.map(([title, text], i) => (
            <div key={title} className="flex items-center gap-3 rounded-2xl bg-surface px-3.5 py-3 md:py-4">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary font-bold text-white">
                {i + 1}
              </span>
              <div>
                <div className="text-[15px] font-bold">{title}</div>
                <div className="text-[13px] text-muted">{text}</div>
              </div>
            </div>
          ))}
        </section>
      </main>

      <footer className="mx-auto flex w-full max-w-[1200px] flex-col gap-2 px-5 pb-5 pt-3.5 md:px-6">
        <StoreBar />
        <p className="m-0 text-xs text-muted">
          Purchases happen on the original store&apos;s site.{" "}
          <Link href="/terms">Terms</Link> · <Link href="/privacy">Privacy</Link>
        </p>
      </footer>
    </div>
  );
}
