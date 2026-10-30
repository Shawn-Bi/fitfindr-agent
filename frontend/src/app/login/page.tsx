"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthLayout, FormMessage, PasswordField, PrimaryButton, TextField } from "@/components/AuthForm";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { Profile } from "@/lib/types";

function safeNext(next: string | null): string | null {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

function Login() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string; unverified?: boolean }>({});

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!email.trim()) next.email = "Enter the email you signed up with.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    if (Object.keys(next).length) return;

    setBusy(true);
    const { error } = await supabase().auth.signInWithPassword({ email: email.trim(), password });
    if (error) {
      setBusy(false);
      const msg = error.message.toLowerCase();
      if (msg.includes("not confirmed")) {
        setErrors({ form: "Please verify your email first. Check your inbox for the link we sent.", unverified: true });
      } else if (msg.includes("invalid")) {
        setErrors({ form: "That email and password don't match. Check both, or reset your password." });
      } else if (error.status === 429) {
        setErrors({ form: "Too many attempts. Please wait a minute and try again." });
      } else {
        setErrors({ form: "We couldn't log you in just now. Please try again." });
      }
      return;
    }
    let dest = safeNext(params.get("next"));
    if (!dest) {
      try {
        const profile = await api<Profile>("/profile");
        dest = profile.onboarded ? "/home" : "/onboarding";
      } catch {
        dest = "/home";
      }
    }
    router.replace(dest);
  }

  async function resend() {
    await supabase().auth.resend({
      type: "signup",
      email: email.trim(),
      options: { emailRedirectTo: `${window.location.origin}/onboarding` },
    });
    setErrors({ form: "We sent a new verification link. It can take a minute to arrive." });
  }

  return (
    <AuthLayout title="Log in" subtitle="Welcome back.">
      <form onSubmit={submit} noValidate className="flex flex-col gap-4 pt-5">
        {errors.form && <FormMessage>{errors.form}</FormMessage>}
        {errors.unverified && (
          <button type="button" onClick={resend} className="h-11 self-start font-bold text-primary underline">
            Resend the verification link
          </button>
        )}
        <TextField
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.email}
        />
        <PasswordField autoComplete="current-password" value={password} onChange={setPassword} error={errors.password} />
        <Link href="/forgot-password" className="-mt-1 flex h-11 items-center self-start text-sm font-bold">
          Forgot password?
        </Link>
        <PrimaryButton type="submit" busy={busy}>
          Log in
        </PrimaryButton>
        <p className="m-0 text-center text-sm text-muted">
          New to FitFindr?{" "}
          <Link href="/signup" className="font-bold">
            Create an account
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

export default function Page() {
  return (
    <Suspense>
      <Login />
    </Suspense>
  );
}
