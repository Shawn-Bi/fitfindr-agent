"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthLayout, FormMessage, PrimaryButton, TextField } from "@/components/AuthForm";
import { supabase } from "@/lib/supabase";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return setError("Enter the email you signed up with.");
    setBusy(true);
    setError(null);
    const { error: err } = await supabase().auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    setBusy(false);
    if (err && err.status === 429) return setError("Too many requests. Please wait a minute and try again.");
    // Same message whether or not the account exists.
    setSent(true);
  }

  return (
    <AuthLayout title="Reset your password" subtitle="We'll email you a link to choose a new one." back="/login">
      <form onSubmit={submit} noValidate className="flex flex-col gap-4 pt-5">
        {sent && (
          <FormMessage kind="info">
            If an account exists for {email.trim()}, a reset link is on its way. Open it on this device.
          </FormMessage>
        )}
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          inputMode="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={error}
        />
        <PrimaryButton type="submit" busy={busy}>
          Send reset link
        </PrimaryButton>
        <Link href="/login" className="text-center text-sm font-bold">
          Back to log in
        </Link>
      </form>
    </AuthLayout>
  );
}
