"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ClosetItemForm } from "@/components/ClosetItemForm";
import { RequireAuth } from "@/components/RequireAuth";
import { ErrorBox, Spinner } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import type { ClosetItem } from "@/lib/types";

function EditItem() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [item, setItem] = useState<ClosetItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<ClosetItem>(`/closet/items/${id}`)
      .then(setItem)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load this item."));
  }, [id]);

  return (
    <AppShell>
      <div className="mx-auto max-w-[640px] px-4 md:px-6 md:pt-6">
        <header className="flex items-center justify-between py-3">
          <Link href={`/closet/${id}`} className="flex h-11 items-center font-bold">
            Cancel
          </Link>
          <h1 className="m-0 font-heading text-xl font-bold">Edit item</h1>
          <span className="w-[52px]" aria-hidden="true" />
        </header>
        {error && <ErrorBox message={error} />}
        {!item && !error && <Spinner />}
        {item && <ClosetItemForm item={item} onSaved={() => router.push(`/closet/${id}`)} />}
      </div>
    </AppShell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <EditItem />
    </RequireAuth>
  );
}
