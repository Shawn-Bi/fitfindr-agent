"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { HangerIcon, HeartIcon, HomeIcon, UserIcon } from "./Icons";
import { Logo } from "./Logo";
import { SearchBox } from "./SearchBox";

const NAV = [
  { href: "/home", label: "Home", Icon: HomeIcon },
  { href: "/closet", label: "Closet", Icon: HangerIcon },
  { href: "/saved", label: "Saved", Icon: HeartIcon },
  { href: "/profile", label: "Profile", Icon: UserIcon },
];

function isActive(pathname: string, href: string) {
  if (href === "/home") return pathname === "/home" || pathname.startsWith("/search");
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Signed-in layout: a top bar with search and nav on desktop (md and up),
 * a bottom nav on phones. Guests see Log in / Get started instead.
 */
export function AppShell({
  children,
  searchInitial = "",
  desktopSearch = true,
}: {
  children: React.ReactNode;
  searchInitial?: string;
  desktopSearch?: boolean;
}) {
  const pathname = usePathname();
  const { session, loading } = useAuth();
  const signedIn = !!session;

  return (
    <div className="min-h-dvh">
      <a href="#main" className="sr-only-focusable absolute left-2 top-2 z-50 rounded bg-surface px-3 py-2">
        Skip to content
      </a>
      <header className="hidden border-b border-line-blue bg-surface md:block">
        <div className="mx-auto flex max-w-[1200px] items-center gap-5 px-6 py-3.5">
          <Logo href={signedIn ? "/home" : "/"} />
          {desktopSearch ? (
            <SearchBox
              variant="desktop"
              initial={searchInitial}
              placeholder="Search 6 secondhand stores, e.g. vintage white shirt under $30"
            />
          ) : (
            <div className="flex-1" />
          )}
          {signedIn ? (
            <nav aria-label="Main" className="flex gap-1">
              {NAV.map(({ href, label }) => {
                const active = isActive(pathname, href);
                return (
                  <Link
                    key={href}
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={`flex h-11 items-center rounded-[10px] px-3.5 no-underline ${
                      active ? "bg-tint font-bold text-primary-hover" : "text-ink hover:bg-bg hover:text-ink"
                    }`}
                  >
                    {label}
                  </Link>
                );
              })}
            </nav>
          ) : (
            !loading && (
              <nav aria-label="Account" className="flex items-center gap-2">
                <Link href="/login" className="flex h-11 items-center px-3 font-bold text-ink no-underline hover:text-primary">
                  Log in
                </Link>
                <Link
                  href="/signup"
                  className="flex h-11 items-center rounded-xl bg-primary px-4 font-bold text-white no-underline hover:bg-primary-hover hover:text-white"
                >
                  Get started
                </Link>
              </nav>
            )
          )}
        </div>
      </header>

      <main id="main" className={signedIn ? "pb-24 md:pb-10" : "pb-10"}>
        {children}
      </main>

      {signedIn && (
        <nav
          aria-label="Main"
          className="fixed inset-x-0 bottom-0 z-40 grid h-[72px] grid-cols-4 border-t border-line-soft bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
        >
          {NAV.map(({ href, label, Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center justify-center gap-[3px] text-xs no-underline ${
                  active ? "font-bold text-primary" : "text-muted hover:text-ink"
                }`}
              >
                <Icon />
                {label}
              </Link>
            );
          })}
        </nav>
      )}
    </div>
  );
}
