"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthLayout, FormMessage } from "@/components/AuthForm";
import { supabase } from "@/lib/supabase";

function CheckEmail() {
  const email = useSearchParams().get("email") || "";
  const [note, setNote] = useState<{ kind: "info" | "error"; text: string } | null>(null);

  async function resend() {
    if (!email) return;
    const { error } = await supabase().auth.resend({
      type: "signup",
      email,
      options: { emailRedirectTo: `${window.location.origin}/onboarding` },
    });
    setNote(
      error
        ? { kind: "error", text: "We couldn't resend just now. Wait a minute and try again." }
        : { kind: "info", text: "Sent again. It can take a minute to arrive." },
    );
  }

  return (
    <AuthLayout title="Check your email" back="/signup">
      <div className="flex flex-col gap-4 pt-4 text-[15px] leading-relaxed">
        <p className="m-0">
          We sent a verification link to {email ? <strong>{email}</strong> : "your email address"}. Open it on this
          device to finish creating your account.
        </p>
        <p className="m-0 text-muted">Didn&apos;t get it? Check your spam folder, or send it again.</p>
        {note && <FormMessage kind={note.kind}>{note.text}</FormMessage>}
        <button
          type="button"
          onClick={resend}
          disabled={!email}
          className="h-12 rounded-xl border-[1.5px] border-ink bg-surface font-bold hover:bg-tint disabled:opacity-60"
        >
          Resend the link
        </button>
        <Link href="/login" className="text-center font-bold">
          I&apos;ve verified — log in
        </Link>
      </div>
    </AuthLayout>
  );
}

export default function Page() {
  return (
    <Suspense>
      <CheckEmail />
    </Suspense>
  );
}
