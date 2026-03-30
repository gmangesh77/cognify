"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TrendBadge } from "@/components/common/trend-badge";
import { DomainBadge } from "@/components/common/domain-badge";
import type { RankedTopic, ContentTone, ArticleParams } from "@/types/api";

const TONE_OPTIONS: { value: ContentTone; label: string }[] = [
  { value: "technical-authoritative", label: "Technical & Authoritative" },
  { value: "conversational", label: "Conversational" },
  { value: "educational", label: "Educational" },
  { value: "analytical", label: "Analytical" },
  { value: "news-reporting", label: "News Reporting" },
];

interface GenerateArticleModalProps {
  topic: RankedTopic | null;
  onClose: () => void;
  onConfirm: (topic: RankedTopic, articleParams?: ArticleParams) => void;
}

export function GenerateArticleModal({
  topic,
  onClose,
  onConfirm,
}: GenerateArticleModalProps) {
  const [expanded, setExpanded] = useState(false);
  const [audience, setAudience] = useState("");
  const [tone, setTone] = useState<ContentTone>("technical-authoritative");
  const [angle, setAngle] = useState("");

  if (!topic) return null;

  function handleConfirm() {
    const params: ArticleParams | undefined = expanded
      ? {
          target_audience: audience || undefined,
          content_tone: tone,
          preferred_angle: angle || undefined,
        }
      : undefined;
    onConfirm(topic!, params);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        role="dialog"
        className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-heading text-lg font-semibold text-neutral-900">
          Generate Article
        </h2>
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2">
            <TrendBadge variant={topic.trend_status} />
            <DomainBadge domain={topic.domain} />
          </div>
          <h3 className="font-heading text-base font-medium text-neutral-900">
            {topic.title}
          </h3>
          <p className="text-sm text-neutral-500">{topic.description}</p>
          <p className="text-sm text-neutral-500">
            Score:{" "}
            <span className="font-semibold text-neutral-900">
              {topic.composite_score}
            </span>
          </p>
        </div>

        {/* Customize Article section */}
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="mt-4 flex w-full items-center justify-between rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-600 hover:bg-neutral-50"
        >
          <span>Customize Article</span>
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>

        {expanded && (
          <div className="mt-3 space-y-3 rounded-md border border-neutral-100 p-3">
            <div>
              <label className="text-xs font-medium text-neutral-500">
                Target Audience
              </label>
              <input
                type="text"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="e.g., Security engineers and CTOs"
                className="mt-1 w-full rounded-md border border-neutral-200 px-3 py-1.5 text-sm focus:border-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-neutral-500">
                Content Tone
              </label>
              <select
                value={tone}
                onChange={(e) => setTone(e.target.value as ContentTone)}
                className="mt-1 w-full rounded-md border border-neutral-200 px-3 py-1.5 text-sm focus:border-primary focus:outline-none"
              >
                {TONE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-neutral-500">
                Preferred Angle
              </label>
              <input
                type="text"
                value={angle}
                onChange={(e) => setAngle(e.target.value)}
                placeholder="e.g., Practical implementation guide"
                className="mt-1 w-full rounded-md border border-neutral-200 px-3 py-1.5 text-sm focus:border-primary focus:outline-none"
              />
            </div>
          </div>
        )}

        <p className="mt-4 text-sm text-neutral-500">
          This will start the content generation pipeline. Estimated time: 2-5
          minutes.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleConfirm}>Generate</Button>
        </div>
      </div>
    </div>
  );
}
