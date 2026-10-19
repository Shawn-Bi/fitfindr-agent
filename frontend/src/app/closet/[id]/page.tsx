"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { BackIcon, TrashIcon } from "@/components/Icons";
import { ListingCard } from "@/components/ListingCard";
import { RequireAuth } from "@/components/RequireAuth";
import { ErrorBox, SkeletonGrid, Spinner } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import { CATEGORIES } from "@/lib/format";
import type { ClosetItem, Pick } from "@/lib/types";

function Detail({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex gap-3 border-b border-line-soft py-2.5 text-sm last:border-0">
      <dt className="w-24 shrink-0 text-muted">{label}</dt>
      <dd className="m-0">{value}</dd>
    </div>
  );
}

/** P8 Closet item detail: photo, details, Edit/Delete, "Finds that go with this". */
function ItemDetail() {
  const { id } = useParams<{ id: string }>();
  const added = useSearchParams().get("added") === "1";
  const router = useRouter();
  const [item, setItem] = useState<ClosetItem | null>(null);
  const [matches, setMatches] = useState<Pick[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    api<ClosetItem>(`/closet/items/${id}`)
      .then(setItem)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load this item."));
    api<{ matches: Pick[] }>(`/closet/items/${id}/matches`)
      .then((d) => setMatches(d.matches))
      .catch(() => setMatches([]));
  }, [id]);

  async function remove() {
    setDeleting(true);
    try {
      await api(`/closet/items/${id}`, { method: "DELETE" });
      router.replace("/closet");
    } catch (e) {
      setDeleting(false);
      setConfirm(false);
      setError(e instanceof ApiError ? e.message : "Couldn't delete this item.");
    }
  }

  const category = CATEGORIES.find((c) => c.key === item?.category)?.label;

  return (
    <AppShell>
      <div className="mx-auto max-w-[1200px] md:px-6 md:pt-6">
        {error && (
          <div className="p-4 md:px-0">
            <ErrorBox message={error} />
            <Link href="/closet" className="mt-3 inline-flex h-11 items-center font-bold">
              Back to closet
            </Link>
          </div>
        )}
        {!item && !error && (
          <div className="p-6">
            <Spinner />
          </div>
        )}
        {item && (
          <div className="md:grid md:grid-cols-[minmax(0,420px)_1fr] md:gap-8">
            <div className="relative">
              {item.photo ? (
                // eslint-disable-next-line @next/next/no-img-element -- signed Supabase URL
                <img
                  src={item.photo}
                  alt={`Your photo of ${item.name}`}
                  className="h-[380px] w-full bg-line-soft object-cover md:h-[520px] md:rounded-[18px]"
                />
              ) : (
                <div className="h-[380px] w-full bg-line-soft md:rounded-[18px]" />
              )}
              <Link
                href="/closet"
                aria-label="Back to closet"
                className="absolute left-3 top-3 flex h-11 w-11 items-center justify-center rounded-full bg-surface/90 text-ink"
              >
                <BackIcon />
              </Link>
              <div className="absolute right-3 top-3 flex gap-2">
                <Link
                  href={`/closet/${item.id}/edit`}
                  className="flex h-11 items-center rounded-full bg-surface/90 px-4 font-bold text-ink no-underline hover:text-primary"
                >
                  Edit
                </Link>
                <button
                  type="button"
                  aria-label="Delete item"
                  onClick={() => setConfirm(true)}
                  className="flex h-11 w-11 items-center justify-center rounded-full bg-surface/90 text-danger"
                >
                  <TrashIcon />
                </button>
              </div>
            </div>

            <div className="flex flex-col gap-4 px-4 pt-4 md:px-0 md:pt-0">
              {added && (
                <div role="status" className="rounded-xl bg-tint p-3 text-sm">
                  Saved to your closet. <Link href="/closet/new">Add another item</Link>
                </div>
              )}
              <div>
                <h1 className="m-0 font-heading text-2xl font-bold leading-tight md:text-3xl">{item.name}</h1>
                <div className="mt-1 text-sm text-muted">
                  {[category, item.size, item.brand].filter(Boolean).join(" · ")}
                </div>
              </div>
              <dl className="m-0 rounded-2xl bg-surface px-4 py-1">
                <Detail label="Colors" value={item.colors.join(", ")} />
                <Detail label="Style" value={item.style_tags.join(", ")} />
                <Detail label="Season" value={item.season.join(", ")} />
                <Detail label="Notes" value={item.notes} />
              </dl>

              <section aria-labelledby="finds-title" className="pb-4">
                <h2 id="finds-title" className="mb-2.5 mt-2 font-heading text-lg font-bold">
                  Finds that go with this
                </h2>
                {!matches && <SkeletonGrid count={2} />}
                {matches && matches.length === 0 && (
                  <p className="m-0 rounded-2xl bg-surface p-4 text-sm text-muted">
                    No finds yet. Matches come from recent searches —{" "}
                    <Link href="/home">try a search</Link> and check back.
                  </p>
                )}
                {matches && matches.length > 0 && (
                  <>
                    <div className="no-scrollbar -mx-4 flex gap-3 overflow-x-auto px-4 md:mx-0 md:grid md:grid-cols-3 md:overflow-visible md:px-0">
                      {matches.map((m) => (
                        <div key={`${m.listing.platform}-${m.listing.id}`} className="w-[170px] shrink-0 md:w-auto">
                          <ListingCard listing={m.listing} reason={m.reason} />
                        </div>
                      ))}
                    </div>
                    <p className="mb-0 mt-2 text-xs text-muted">Price and stock may change on the original site.</p>
                  </>
                )}
              </section>
            </div>
          </div>
        )}
      </div>
      <ConfirmDialog
        open={confirm}
        title="Delete this item?"
        confirmLabel="Delete"
        busy={deleting}
        onConfirm={remove}
        onCancel={() => setConfirm(false)}
      >
        {item?.name} and its photo will be removed from your closet. This can&apos;t be undone.
      </ConfirmDialog>
    </AppShell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Suspense>
        <ItemDetail />
      </Suspense>
    </RequireAuth>
  );
}
