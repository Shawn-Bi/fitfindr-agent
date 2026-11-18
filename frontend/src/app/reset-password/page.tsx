"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { AuthLayout, FormMessage, PasswordField, PrimaryButton } from "@/components/AuthForm";
import { supabase } from "@/lib/supabase";

/** Opened from the reset email: Supabase signs the user in from the link, then they pick a new password. */
export default function ResetPassword() {
  const router = useRouter();
  const { session, loading } = useAuth();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 12) return setError(`Use at least 12 characters (you have ${password.length}).`);
    setBusy(true);
    const { error: err } = await supabase().auth.updateUser({ password });
    setBusy(false);
    if (err) return setError(err.message.includes("different") ? err.message : "We couldn't update your password. Try the link again.");
    router.replace("/home");
  }

  return (
    <AuthLayout title="Choose a new password" back="/login">
      {!loading && !session ? (
        <div className="flex flex-col gap-4 pt-5">
          <FormMessage>This reset link has expired or was already used. Ask for a new one.</FormMessage>
          <Link href="/forgot-password" className="font-bold">
            Send a new reset link
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4 pt-5">
          <PasswordField
            label="New password"
            autoComplete="new-password"
            value={password}
            onChange={setPassword}
            hint="Use 12 or more characters."
            error={error}
          />
          <PrimaryButton type="submit" busy={busy}>
            Save new password
          </PrimaryButton>
        </form>
      )}
    </AuthLayout>
  );
}
