"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { BackIcon } from "./Icons";
import { LogoMark } from "./Logo";

/** Phone: full-width form like the SignUp prototype. Desktop: centered card. */
export function AuthLayout({ step, title, subtitle, children, footer, back = "/" }: {
  step?: string;
  title: string;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  back?: string;
}) {
  return (
    <div className="flex min-h-dvh flex-col md:items-center md:justify-center md:py-10">
      <div className="flex w-full flex-1 flex-col md:max-w-[460px] md:flex-none md:rounded-3xl md:bg-surface md:p-8 md:shadow-sm">
        <header className="flex items-center gap-3 px-3 py-3.5 md:px-0 md:pt-0">
          <Link href={back} aria-label="Back" className="flex h-11 w-11 items-center justify-center text-ink hover:text-primary">
            <BackIcon />
          </Link>
          <Link href="/" className="flex items-center gap-1.5 font-heading text-xl font-bold text-ink no-underline hover:text-ink">
            <LogoMark size={30} />
            <span>
              Fit<span className="text-accent">Findr</span>
            </span>
          </Link>
        </header>
        <main id="main" className="flex flex-1 flex-col px-5 md:px-0">
          <div className="flex flex-col gap-1.5 pt-2">
            {step && <div className="text-[13px] font-medium text-muted">{step}</div>}
            <h1 className="m-0 font-heading text-[30px] font-bold tracking-[-0.5px]">{title}</h1>
            {subtitle && <p className="m-0 text-[15px] text-muted">{subtitle}</p>}
          </div>
          {children}
          {footer && <div className="mt-auto pb-5 pt-6 text-xs leading-normal text-muted">{footer}</div>}
        </main>
      </div>
    </div>
  );
}

export function TextField({ label, error, ...props }: React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string | null;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-bold">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-err` : undefined}
        className="h-[50px] rounded-xl border-[1.5px] border-line bg-surface px-3.5 text-base text-ink outline-none focus:border-primary aria-[invalid=true]:border-danger"
        {...props}
      />
      {error && (
        <div id={`${id}-err`} className="text-[13px] text-danger">
          {error}
        </div>
      )}
    </div>
  );
}

export function PasswordField({ label = "Password", hint, error, autoComplete, value, onChange }: {
  label?: string;
  hint?: string;
  error?: string | null;
  autoComplete: "new-password" | "current-password";
  value: string;
  onChange: (v: string) => void;
}) {
  const id = useId();
  const [show, setShow] = useState(false);
  const described = [hint && `${id}-hint`, error && `${id}-err`].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-bold">
        {label}
      </label>
      <div className="flex h-[50px] items-center rounded-xl border-[1.5px] border-line bg-surface pl-3.5 focus-within:border-primary">
        <input
          id={id}
          name="password"
          type={show ? "text" : "password"}
          autoComplete={autoComplete}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={autoComplete === "new-password" ? "At least 12 characters" : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={described}
          className="h-full min-w-0 flex-1 border-0 bg-transparent text-base text-ink outline-none"
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          aria-pressed={show}
          aria-label={show ? "Hide password" : "Show password"}
          className="h-11 px-3.5 text-sm font-bold text-primary hover:text-primary-hover"
        >
          {show ? "Hide" : "Show"}
        </button>
      </div>
      {hint && (
        <div id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </div>
      )}
      {error && (
        <div id={`${id}-err`} className="text-[13px] text-danger">
          {error}
        </div>
      )}
    </div>
  );
}

export function PrimaryButton({ children, busy, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button
      {...props}
      disabled={busy || props.disabled}
      className={`flex h-[52px] w-full items-center justify-center rounded-2xl bg-primary text-base font-bold text-white hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60 ${props.className || ""}`}
    >
      {busy ? "Please wait…" : children}
    </button>
  );
}

export function FormMessage({ kind = "error", children }: { kind?: "error" | "info"; children: React.ReactNode }) {
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={`rounded-xl p-3 text-sm ${kind === "error" ? "bg-[#FDECEA] text-danger" : "bg-tint text-ink"}`}
    >
      {children}
    </div>
  );
}
