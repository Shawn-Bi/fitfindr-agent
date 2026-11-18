"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { ClosetItemForm } from "@/components/ClosetItemForm";
import { RequireAuth } from "@/components/RequireAuth";

/** P7 Add item. */
function AddItem() {
  const router = useRouter();
  return (
    <AppShell>
      <div className="mx-auto max-w-[640px] px-4 md:px-6 md:pt-6">
        <header className="flex items-center justify-between py-3">
          <Link href="/closet" className="flex h-11 items-center font-bold">
            Cancel
          </Link>
          <h1 className="m-0 font-heading text-xl font-bold">Add item</h1>
          <span className="w-[52px]" aria-hidden="true" />
        </header>
        <ClosetItemForm onSaved={(item) => router.push(`/closet/${item.id}?added=1`)} />
      </div>
    </AppShell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <AddItem />
    </RequireAuth>
  );
}
