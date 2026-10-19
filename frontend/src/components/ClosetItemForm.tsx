"use client";

import { useEffect, useId, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { CATEGORIES, COLOR_SWATCHES } from "@/lib/format";
import type { Category, ClosetItem } from "@/lib/types";
import { FormMessage, PrimaryButton } from "./AuthForm";
import { CameraIcon } from "./Icons";
import { Swatch, ToggleChip } from "./ProfileForm";

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT = "image/jpeg,image/png,image/heic,image/heif,.heic,.heif,.jpg,.jpeg,.png";
const TAGS = ["vintage", "streetwear", "minimalist", "y2k", "grunge", "cottagecore", "denim", "baggy", "fitted", "oversized", "knit", "leather"];
const SEASONS = ["spring", "summer", "fall", "winter"];

function checkFile(file: File): string | null {
  const name = file.name.toLowerCase();
  const okType = /^image\/(jpeg|png|heic|heif)$/.test(file.type) || /\.(jpe?g|png|heic|heif)$/.test(name);
  if (!okType) return "That file type isn't supported. Use a JPG, PNG or HEIC photo.";
  if (file.size > MAX_BYTES) return `That photo is ${(file.size / 1048576).toFixed(1)} MB. Photos must be 10 MB or smaller.`;
  return null;
}

function toggle(list: string[], value: string) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function Field({ label, children, required, error, hint }: {
  label: string;
  children: (id: string) => React.ReactNode;
  required?: boolean;
  error?: string;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-bold">
        {label} {required && <span className="text-danger" aria-hidden="true">*</span>}
        {required && <span className="sr-only">(required)</span>}
      </label>
      {children(id)}
      {hint && <div className="text-xs text-muted">{hint}</div>}
      {error && <div className="text-[13px] text-danger">{error}</div>}
    </div>
  );
}

const inputCls =
  "h-12 rounded-xl border-[1.5px] border-line bg-surface px-3.5 text-base text-ink outline-none focus:border-primary";

/** P7 Add item (and Edit): photo first, then the details from PRD section 4. */
export function ClosetItemForm({ item, onSaved }: { item?: ClosetItem; onSaved: (item: ClosetItem) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [name, setName] = useState(item?.name || "");
  const [category, setCategory] = useState<Category | "">(item?.category || "");
  const [colors, setColors] = useState<string[]>(item?.colors || []);
  const [tags, setTags] = useState<string[]>(item?.style_tags || []);
  const [customTag, setCustomTag] = useState("");
  const [size, setSize] = useState(item?.size || "");
  const [brand, setBrand] = useState(item?.brand || "");
  const [season, setSeason] = useState<string[]>(item?.season || []);
  const [notes, setNotes] = useState(item?.notes || "");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const cameraRef = useRef<HTMLInputElement>(null);
  const libraryRef = useRef<HTMLInputElement>(null);
  const extraColors = item?.colors.filter((c) => !COLOR_SWATCHES.some((s) => s.name === c)) || [];

  useEffect(() => {
    if (!file) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function pick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    const problem = checkFile(f);
    if (problem) {
      setErrors({ ...errors, photo: problem });
      return;
    }
    setErrors({ ...errors, photo: "" });
    setFile(f);
  }

  function addTag() {
    const t = customTag.trim().toLowerCase();
    if (t && !tags.includes(t)) setTags([...tags, t]);
    setCustomTag("");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!item && !file) next.photo = "Add a photo of the item.";
    if (!name.trim()) next.name = "Give the item a name, like “Baggy straight-leg jeans”.";
    if (!category) next.category = "Pick a category.";
    if (colors.length === 0) next.colors = "Pick at least one color.";
    setErrors(next);
    if (Object.values(next).some(Boolean)) {
      document.querySelector<HTMLElement>("[data-error='true']")?.scrollIntoView({ block: "center" });
      return;
    }
    const fields = { name: name.trim(), category, colors, style_tags: tags, size, brand, season, notes };
    setBusy(true);
    try {
      let saved: ClosetItem;
      if (item) {
        saved = await api<ClosetItem>(`/closet/items/${item.id}`, { method: "PATCH", json: fields });
        if (file) {
          const form = new FormData();
          form.append("photo", file);
          saved = await api<ClosetItem>(`/closet/items/${item.id}/photo`, { form });
        }
      } else {
        const form = new FormData();
        form.append("data", JSON.stringify(fields));
        form.append("photo", file as File);
        saved = await api<ClosetItem>("/closet/items", { form });
      }
      onSaved(saved);
    } catch (err) {
      setErrors({ form: err instanceof ApiError ? err.message : "Saving failed. Check your connection and try again." });
    } finally {
      setBusy(false);
    }
  }

  const shownPhoto = preview || item?.photo || null;
  const isHeic = file && /hei[cf]/i.test(file.type + file.name);

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      {errors.form && (
        <FormMessage>
          {errors.form} Your details are still here — press Save to try again.
        </FormMessage>
      )}

      <section className="flex flex-col gap-2" data-error={!!errors.photo}>
        <h2 className="m-0 text-sm font-bold">
          Photo {!item && <span className="text-danger" aria-hidden="true">*</span>}
        </h2>
        {shownPhoto && !isHeic ? (
          // eslint-disable-next-line @next/next/no-img-element -- local preview or signed URL
          <img src={shownPhoto} alt="Your photo of the item" className="h-[280px] w-full rounded-2xl bg-line-soft object-contain md:h-[340px]" />
        ) : file ? (
          <div className="flex h-[200px] items-center justify-center rounded-2xl bg-tint p-4 text-center text-sm">
            HEIC photo selected ({file.name}). It will be converted when you save.
          </div>
        ) : (
          <div className="flex h-[200px] flex-col items-center justify-center gap-2 rounded-2xl border-[1.5px] border-dashed border-line bg-surface text-muted">
            <CameraIcon size={32} />
            <span className="text-sm">JPG, PNG or HEIC · up to 10 MB</span>
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => cameraRef.current?.click()}
            className="h-11 rounded-xl border-[1.5px] border-ink bg-surface px-4 text-sm font-bold hover:bg-tint"
          >
            {file || item ? "Retake photo" : "Take photo"}
          </button>
          <button
            type="button"
            onClick={() => libraryRef.current?.click()}
            className="h-11 rounded-xl border-[1.5px] border-ink bg-surface px-4 text-sm font-bold hover:bg-tint"
          >
            Choose from library
          </button>
          {file && (
            <button type="button" onClick={() => setFile(null)} className="h-11 px-3 text-sm font-bold text-danger">
              Remove photo
            </button>
          )}
        </div>
        <input ref={cameraRef} type="file" accept={ACCEPT} capture="environment" onChange={pick} className="hidden" aria-hidden="true" tabIndex={-1} />
        <input ref={libraryRef} type="file" accept={ACCEPT} onChange={pick} className="hidden" aria-label="Choose a photo from your library" />
        {errors.photo && (
          <div role="alert" className="text-[13px] text-danger">
            {errors.photo}
          </div>
        )}
      </section>

      <div data-error={!!errors.name}>
        <Field label="Name" required error={errors.name}>
          {(id) => (
            <input
              id={id}
              className={inputCls}
              value={name}
              maxLength={80}
              onChange={(e) => setName(e.target.value)}
              placeholder="Baggy straight-leg jeans"
            />
          )}
        </Field>
      </div>

      <fieldset className="m-0 border-0 p-0" data-error={!!errors.category}>
        <legend className="mb-2 p-0 text-sm font-bold">
          Category <span className="text-danger" aria-hidden="true">*</span>
          <span className="sr-only">(required)</span>
        </legend>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((c) => (
            <ToggleChip key={c.key} pressed={category === c.key} onClick={() => setCategory(c.key)}>
              {c.label}
            </ToggleChip>
          ))}
        </div>
        {errors.category && <div className="mt-1.5 text-[13px] text-danger">{errors.category}</div>}
      </fieldset>

      <fieldset className="m-0 border-0 p-0" data-error={!!errors.colors}>
        <legend className="mb-2 p-0 text-sm font-bold">
          Colors <span className="text-danger" aria-hidden="true">*</span>
          <span className="sr-only">(required, pick one or more)</span>
        </legend>
        <div className="flex flex-wrap gap-2.5">
          {COLOR_SWATCHES.map((c) => (
            <Swatch key={c.name} {...c} selected={colors.includes(c.name)} onClick={() => setColors(toggle(colors, c.name))} />
          ))}
          {extraColors.map((c) => (
            <ToggleChip key={c} pressed={colors.includes(c)} onClick={() => setColors(toggle(colors, c))}>
              {c}
            </ToggleChip>
          ))}
        </div>
        <div className="mt-1.5 text-xs text-muted" aria-live="polite">
          {colors.length ? `Selected: ${colors.join(", ")}` : "Pick every color the item has."}
        </div>
        {errors.colors && <div className="mt-1 text-[13px] text-danger">{errors.colors}</div>}
      </fieldset>

      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-2 p-0 text-sm font-bold">Style tags</legend>
        <div className="flex flex-wrap gap-2">
          {[...TAGS, ...tags.filter((t) => !TAGS.includes(t))].map((t) => (
            <ToggleChip key={t} pressed={tags.includes(t)} onClick={() => setTags(toggle(tags, t))}>
              {t}
            </ToggleChip>
          ))}
        </div>
        <div className="mt-2 flex gap-2">
          <label htmlFor="custom-tag" className="sr-only">
            Add your own tag
          </label>
          <input
            id="custom-tag"
            className={`${inputCls} h-11 min-w-0 flex-1`}
            value={customTag}
            maxLength={30}
            placeholder="+ add tag"
            onChange={(e) => setCustomTag(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addTag();
              }
            }}
          />
          <button type="button" onClick={addTag} className="h-11 rounded-xl border-[1.5px] border-ink bg-surface px-4 text-sm font-bold">
            Add
          </button>
        </div>
      </fieldset>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Size">
          {(id) => <input id={id} className={inputCls} value={size} maxLength={20} onChange={(e) => setSize(e.target.value)} placeholder="W30 L32" />}
        </Field>
        <Field label="Brand">
          {(id) => <input id={id} className={inputCls} value={brand} maxLength={40} onChange={(e) => setBrand(e.target.value)} placeholder="Optional" />}
        </Field>
      </div>

      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-2 p-0 text-sm font-bold">Season</legend>
        <div className="flex flex-wrap gap-2">
          {SEASONS.map((s) => (
            <ToggleChip key={s} pressed={season.includes(s)} onClick={() => setSeason(toggle(season, s))}>
              {s}
            </ToggleChip>
          ))}
        </div>
      </fieldset>

      <Field label="Notes">
        {(id) => (
          <textarea
            id={id}
            rows={3}
            maxLength={300}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="High-waisted, sits above the hip"
            className="rounded-xl border-[1.5px] border-line bg-surface px-3.5 py-3 text-base outline-none focus:border-primary"
          />
        )}
      </Field>

      <PrimaryButton type="submit" busy={busy}>
        {item ? "Save changes" : "Save to closet"}
      </PrimaryButton>
      {busy && !item && <p className="m-0 text-center text-xs text-muted">Uploading your photo…</p>}
    </form>
  );
}
