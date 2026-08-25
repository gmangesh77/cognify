"use client";

import { useState, type ReactNode } from "react";
import { Pencil } from "lucide-react";
import {
  Counter,
  MetadataField,
  RegenButton,
} from "@/components/articles/article-metadata-fields";
import { ArticleStatusControl } from "@/components/articles/article-status-control";
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

interface ArticleHeaderEditorProps {
  article: ArticleDetail;
  children?: ReactNode;
}

export function ArticleHeaderEditor({ article, children }: ArticleHeaderEditorProps) {
  const { save, saving, regenerate, regenerating } = useArticleMetadata(article.id);
  const [form, setForm] = useState<FormState | null>(null);
  const [warnings, setWarnings] = useState<FieldWarning[]>([]);
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof FormState) => (value: string) =>
    setForm((f) => (f ? { ...f, [key]: value } : f));

  const fill = (key: "seoTitle" | "seoDescription" | "keywords", field: SeoRegenerateField) =>
    void regenerate(field)
      .then((res) => {
        setError(null);
        const value = Array.isArray(res.value) ? res.value.join(", ") : res.value;
        set(key)(value);
      })
      .catch(() => setError("Regenerate failed — try again."));

  const canSave =
    form !== null &&
    form.title.trim().length > 0 &&
    Object.keys(buildPatch(article, form)).length > 0;

  const onSave = () => {
    if (!form || !canSave) return;
    setError(null);
    void save(buildPatch(article, form))
      .then((res) => {
        setWarnings(res.warnings);
        setForm(null);
      })
      .catch(() => setError("Save failed — check the fields and try again."));
  };

  if (form === null) {
    return (
      <div>
        <Header title={article.title} subtitle={article.subtitle ?? ""}>
          <ArticleStatusControl
            status={article.status}
            busy={saving}
            onTransition={(next) => {
              setError(null);
              void save({ status: next }).catch(() =>
                setError("Status change failed — try again."),
              );
            }}
          />
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
        {error && (
          <p role="alert" className="mt-2 text-xs text-error">
            {error}
          </p>
        )}
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

  const field = (label: string, key: keyof FormState, extra?: ReactNode) => (
    <MetadataField
      label={label}
      id={`meta-${key}`}
      value={form[key]}
      onChange={set(key)}
      extra={extra}
    />
  );

  const regen = (
    label: string,
    key: "seoTitle" | "seoDescription" | "keywords",
    f: SeoRegenerateField,
  ) => (
    <RegenButton label={label} disabled={regenerating} onClick={() => fill(key, f)} />
  );

  return (
    <div className="space-y-3 rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      {field("Title", "title")}
      {field("Subtitle", "subtitle")}
      {field(
        "SEO title",
        "seoTitle",
        <span className="flex items-center gap-2">
          <Counter id="seo-title-counter" length={form.seoTitle.length} lo={50} hi={60} />
          {regen("Regenerate SEO title", "seoTitle", "seo_title")}
        </span>,
      )}
      {field(
        "SEO description",
        "seoDescription",
        <span className="flex items-center gap-2">
          <Counter id="seo-description-counter" length={form.seoDescription.length} lo={150} hi={160} />
          {regen("Regenerate SEO description", "seoDescription", "seo_description")}
        </span>,
      )}
      {field("Keywords", "keywords", regen("Regenerate keywords", "keywords", "keywords"))}
      {error && (
        <p role="alert" className="text-xs text-error">
          {error}
        </p>
      )}
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
          disabled={saving || !canSave}
          onClick={onSave}
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-white hover:bg-primary/90 disabled:opacity-50"
        >
          Save
        </button>
      </div>
    </div>
  );
}
