"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthLayout, FormMessage, PasswordField, PrimaryButton, TextField } from "@/components/AuthForm";
import { supabase } from "@/lib/supabase";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** P2 Sign up: email + password + required terms checkbox. */
export default function SignUp() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [terms, setTerms] = useState(false);
  const [optIn, setOptIn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string; terms?: string; form?: string }>({});

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!EMAIL_RE.test(email.trim())) next.email = "Enter a valid email address, like you@example.com.";
    if (password.length < 12) next.password = `Use at least 12 characters (you have ${password.length}).`;
    if (!terms) next.terms = "Please agree to the Terms of Service and Privacy Policy to create an account.";
    setErrors(next);
    if (Object.keys(next).length) return;

    setBusy(true);
    const { error } = await supabase().auth.signUp({
      email: email.trim(),
      password,
      options: {
        emailRedirectTo: `${window.location.origin}/onboarding`,
        data: { email_opt_in: optIn, terms_accepted_at: new Date().toISOString() },
      },
    });
    setBusy(false);
    if (error) {
      const msg = error.message.toLowerCase();
      if (msg.includes("password")) setErrors({ password: error.message });
      else if (msg.includes("rate") || error.status === 429)
        setErrors({ form: "Too many sign-up attempts. Please wait a minute and try again." });
      else setErrors({ form: "We couldn't create your account. Check your email address and try again." });
      return;
    }
    router.push(`/check-email?email=${encodeURIComponent(email.trim())}`);
  }

  return (
    <AuthLayout
      step="Step 1 of 2"
      title="Create your account"
      subtitle="Just an email and a password. Everything else is optional."
      footer="We'll send a link to verify your email. Purchases happen on the original store's site; FitFindr never asks for payment details."
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4 pt-5">
        {errors.form && <FormMessage>{errors.form}</FormMessage>}
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
        <PasswordField
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
          hint="Use 12 or more characters. Password managers welcome."
          error={errors.password}
        />

        <div className="flex flex-col gap-1">
          <div className="flex items-start gap-2.5 rounded-xl bg-surface p-3">
            <input
              id="terms"
              type="checkbox"
              checked={terms}
              onChange={(e) => setTerms(e.target.checked)}
              aria-invalid={errors.terms ? true : undefined}
              aria-describedby={errors.terms ? "terms-err" : undefined}
              className="mt-0.5 h-[22px] w-[22px] shrink-0 accent-primary"
            />
            <label htmlFor="terms" className="text-sm leading-snug">
              I agree to the{" "}
              <Link href="/terms" target="_blank">
                Terms of Service
              </Link>{" "}
              and the{" "}
              <Link href="/privacy" target="_blank">
                Privacy Policy
              </Link>
              . <span className="text-muted">(required)</span>
            </label>
          </div>
          {errors.terms && (
            <div id="terms-err" className="px-1 text-[13px] text-danger">
              {errors.terms}
            </div>
          )}
        </div>
        <div className="flex items-start gap-2.5 px-3">
          <input
            id="optin"
            type="checkbox"
            checked={optIn}
            onChange={(e) => setOptIn(e.target.checked)}
            className="mt-0.5 h-[22px] w-[22px] shrink-0 accent-primary"
          />
          <label htmlFor="optin" className="text-sm leading-snug text-muted">
            Email me new matches for my closet. Optional, off by default.
          </label>
        </div>

        <PrimaryButton type="submit" busy={busy} className="mt-1">
          Create account
        </PrimaryButton>
        <p className="m-0 text-center text-sm text-muted">
          Already have an account?{" "}
          <Link href="/login" className="font-bold">
            Log in
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}
