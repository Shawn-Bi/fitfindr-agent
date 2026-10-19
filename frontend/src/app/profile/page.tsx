"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { FormMessage } from "@/components/AuthForm";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ProfileForm } from "@/components/ProfileForm";
import { RequireAuth } from "@/components/RequireAuth";
import { ErrorBox, Spinner } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { Profile } from "@/lib/types";

function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [typed, setTyped] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    api<Profile>("/profile")
      .then(setProfile)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load your profile."));
  }, []);

  async function logOut() {
    await supabase().auth.signOut();
    router.replace("/");
  }

  async function deleteAccount() {
    setDeleting(true);
    setDeleteError(null);
    try {
      await api("/account", { method: "DELETE" });
      await supabase().auth.signOut({ scope: "local" });
      router.replace("/?deleted=1");
    } catch (e) {
      setDeleting(false);
      setDeleteError(e instanceof ApiError ? e.message : "We couldn't delete your account. Please try again.");
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-[640px] px-4 md:px-6 md:pt-6">
        <header className="pb-3 pt-5 md:pt-0">
          <h1 className="m-0 font-heading text-[28px] font-bold tracking-[-0.5px]">Profile</h1>
          {profile?.email && <div className="text-[13px] text-muted">Signed in as {profile.email}</div>}
        </header>
        {error && <ErrorBox message={error} />}
        {!profile && !error && <Spinner />}
        {profile && (
          <div className="flex flex-col gap-8 pb-6">
            <section className="rounded-[18px] bg-surface p-4 md:p-6" aria-labelledby="prefs-title">
              <h2 id="prefs-title" className="mb-1 mt-0 font-heading text-lg font-bold">
                Your sizes and style
              </h2>
              <p className="mb-4 mt-0 text-sm text-muted">Used only to filter and rank finds for you. All optional.</p>
              {saved && (
                <div className="mb-4">
                  <FormMessage kind="info">Saved. New searches use these preferences.</FormMessage>
                </div>
              )}
              <ProfileForm
                initial={profile}
                submitLabel="Save preferences"
                onSaved={(p) => {
                  setProfile(p);
                  setSaved(true);
                }}
              />
            </section>

            <section className="flex flex-col gap-3 rounded-[18px] bg-surface p-4 md:p-6" aria-labelledby="account-title">
              <h2 id="account-title" className="m-0 font-heading text-lg font-bold">
                Account
              </h2>
              <p className="m-0 text-sm text-muted">
                Your closet, photos and profile are visible only to you. Read the{" "}
                <Link href="/terms">Terms</Link> and <Link href="/privacy">Privacy Policy</Link>.
              </p>
              <button
                type="button"
                onClick={logOut}
                className="h-12 rounded-xl border-[1.5px] border-ink bg-surface font-bold hover:bg-tint"
              >
                Log out
              </button>
              <button
                type="button"
                onClick={() => setConfirm(true)}
                className="h-12 rounded-xl font-bold text-danger hover:bg-[#FDECEA]"
              >
                Delete my account
              </button>
            </section>
          </div>
        )}
      </div>
      <ConfirmDialog
        open={confirm}
        title="Delete your account?"
        confirmLabel="Delete forever"
        busy={deleting}
        confirmDisabled={typed.trim().toUpperCase() !== "DELETE"}
        onConfirm={deleteAccount}
        onCancel={() => {
          setConfirm(false);
          setTyped("");
        }}
      >
        <p className="mt-0">
          This immediately and permanently deletes your account, every closet item and photo, your saved items and
          your profile. It can&apos;t be undone.
        </p>
        <label htmlFor="type-delete" className="block text-sm font-bold text-ink">
          Type DELETE to confirm
        </label>
        <input
          id="type-delete"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          autoComplete="off"
          className="mt-1.5 h-12 w-full rounded-xl border-[1.5px] border-line px-3.5 text-base text-ink outline-none focus:border-primary"
        />
        {deleteError && <p className="mb-0 text-sm text-danger">{deleteError}</p>}
      </ConfirmDialog>
    </AppShell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <ProfilePage />
    </RequireAuth>
  );
}
