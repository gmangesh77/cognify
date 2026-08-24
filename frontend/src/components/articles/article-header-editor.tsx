"use client";

import { useState, type ReactNode } from "react";
import { Pencil, RefreshCw } from "lucide-react";
import { Header } from "@/components/layout/header";
import { useArticleMetadata } from "@/hooks/use-article-metadata";
import type {
  ArticleDetail,
  ArticleMetadataPatch,
  FieldWarning,
  SeoRegenerateField,
} from "@/types/articles";

interface FormState {
  title: string;
  subtitle: string;
  seoTitle: string;
  seoDescription: string;
  keywords: string;
}

function formFrom(article: ArticleDetail): FormState {
  return {
    title: article.title,
    subtitle: article.subtitle ?? "",
    seoTitle: article.seo.title,
    seoDescription: article.seo.description,
    keywords: article.seo.keywords.join(", "),
  };
}

function buildPatch(article: ArticleDetail, form: FormState): ArticleMetadataPatch {
  const patch: ArticleMetadataPatch = {};
  if (form.title !== article.title) patch.title = form.title;
  if (form.subtitle !== (article.subtitle ?? "")) patch.subtitle = form.subtitle;
  if (form.seoTitle !== article.seo.title) patch.seo_title = form.seoTitle;
  if (form.seoDescription !== article.seo.description)
    patch.seo_description = form.seoDescription;
  const keywords = form.keywords.split(",").map((k) => k.trim()).filter(Boolean);
  if (keywords.join(",") !== article.seo.keywords.join(","))
    patch.keywords = keywords;
  return patch;
}

function Counter({ id, length, lo, hi }: { id: string; length: number; lo: number; hi: number }) {
  const inRange = length >= lo && length <= hi;
  return (
    <span
      data-testid={id}
      className={`text-xs ${inRange ? "text-neutral-500" : "text-warning"}`}
    >
      {length}/{lo}–{hi}
    </span>
  );
}

interface ArticleHeaderEditorProps {
  article: ArticleDetail;
  children?: ReactNode;
}

export function ArticleHeaderEditor({ article, children }: ArticleHeaderEditorProps) {
  const { save, saving, regenerate, regenerating } = useArticleMetadata(article.id);
  const [form, setForm] = useState<FormState | null>(null);
  const [warnings, setWarnings] = useState<FieldWarning[]>([]);

  const set = (key: keyof FormState) => (value: string) =>
    setForm((f) => (f ? { ...f, [key]: value } : f));

  const fill = (key: "seoTitle" | "seoDescription" | "keywords", field: SeoRegenerateField) =>
    void regenerate(field).then((res) => {
      const value = Array.isArray(res.value) ? res.value.join(", ") : res.value;
      set(key)(value);
    });

  const onSave = () => {
    if (!form) return;
    const patch = buildPatch(article, form);
    if (Object.keys(patch).length === 0) {
      setForm(null);
      return;
    }
    void save(patch).then((res) => {
      setWarnings(res.warnings);
      setForm(null);
    });
  };

  if (form === null) {
    return (
      <div>
        <Header title={article.title} subtitle={article.subtitle ?? ""}>
          {children}
          <button
            type="button"
            aria-label="Edit metadata"
            onClick={() => setForm(formFrom(article))}
            className="rounded-md p-2 text-neutral-600 hover:bg-neutral-100"
          >
            <Pencil className="h-4 w-4" />
          </button>
        </Header>
        {warnings.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs text-warning">
            {warnings.map((w) => (
              <li key={w.field}>{w.message}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  const field = (
    label: string,
    key: keyof FormState,
    extra?: ReactNode,
  ) => (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <label htmlFor={`meta-${key}`} className="text-xs font-medium uppercase tracking-wide text-neutral-500">
          {label}
        </label>
        {extra}
      </div>
      <input
        id={`meta-${key}`}
        value={form[key]}
        onChange={(e) => set(key)(e.target.value)}
        className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-900"
      />
    </div>
  );

  const regenButton = (label: string, key: "seoTitle" | "seoDescription" | "keywords", f: SeoRegenerateField) => (
    <button
      type="button"
      aria-label={label}
      disabled={regenerating}
      onClick={() => fill(key, f)}
      className="rounded-md p-1 text-neutral-500 hover:bg-neutral-100 disabled:opacity-50"
    >
      <RefreshCw className="h-3.5 w-3.5" />
    </button>
  );

  return (
    <div className="space-y-3 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      {field("Title", "title")}
      {field("Subtitle", "subtitle")}
      {field(
        "SEO title",
        "seoTitle",
        <span className="flex items-center gap-2">
          <Counter id="seo-title-counter" length={form.seoTitle.length} lo={50} hi={60} />
          {regenButton("Regenerate SEO title", "seoTitle", "seo_title")}
        </span>,
      )}
      {field(
        "SEO description",
        "seoDescription",
        <span className="flex items-center gap-2">
          <Counter id="seo-description-counter" length={form.seoDescription.length} lo={150} hi={160} />
          {regenButton("Regenerate SEO description", "seoDescription", "seo_description")}
        </span>,
      )}
      {field("Keywords", "keywords", regenButton("Regenerate keywords", "keywords", "keywords"))}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => setForm(null)}
          className="rounded-md px-3 py-1.5 text-sm text-neutral-600 hover:bg-neutral-100"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={saving}
          onClick={onSave}
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-white hover:bg-primary/90 disabled:opacity-50"
        >
          Save
        </button>
      </div>
    </div>
  );
}
