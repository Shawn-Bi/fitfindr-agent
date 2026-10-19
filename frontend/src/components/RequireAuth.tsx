"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "./AuthProvider";
import { Spinner } from "./States";

/** Renders children only when signed in; otherwise sends the visitor to log in. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !session) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, session, router, pathname]);

  if (loading || !session) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner label="Loading" />
      </div>
    );
  }
  return <>{children}</>;
}
