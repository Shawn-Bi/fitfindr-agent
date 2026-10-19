"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ProfileForm } from "@/components/ProfileForm";
import { RequireAuth } from "@/components/RequireAuth";
import { ErrorBox, Spinner } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import type { Profile } from "@/lib/types";

/** P3 Profile setup — every field can be skipped. */
function Onboarding() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [skipping, setSkipping] = useState(false);

  useEffect(() => {
    api<Profile>("/profile")
      .then(setProfile)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load your profile."));
  }, []);

  async function skip() {
    setSkipping(true);
    try {
      await api("/profile", { method: "PATCH", json: {} });
    } catch {
      /* skipping must never trap the user */
    }
    router.push("/closet");
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-[640px] flex-col md:py-10">
      <header className="flex items-center justify-between pb-1 pl-5 pr-3 pt-3.5">
        <div className="text-[13px] font-medium text-muted">Step 2 of 2 · all optional</div>
        <button
          type="button"
          onClick={skip}
          disabled={skipping}
          className="flex h-11 items-center px-2 text-[15px] font-bold text-primary hover:text-primary-hover"
        >
          Skip for now
        </button>
      </header>
      <main id="main" className="flex flex-col gap-4 px-5 pb-8">
        <div className="flex flex-col gap-1.5">
          <h1 className="m-0 font-heading text-[28px] font-bold tracking-[-0.5px]">Your sizes and style</h1>
          <p className="m-0 text-sm text-muted">Used only to filter and rank finds for you. Edit any time in Profile.</p>
        </div>
        {error && <ErrorBox message={error} />}
        {!profile && !error && <Spinner />}
        {profile && (
          <ProfileForm initial={profile} submitLabel="Save and add my first item" onSaved={() => router.push("/closet")} />
        )}
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Onboarding />
    </RequireAuth>
  );
}
