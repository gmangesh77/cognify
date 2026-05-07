"use client";

import { useEffect, useState } from "react";

import { fetchGeneralConfig } from "@/lib/api/settings";
import type { AudiencePersona } from "@/types/settings";

const DEFAULT: AudiencePersona = "general_business";

interface ApiGeneralConfig {
  default_audience_persona?: string;
}

/**
 * Lightweight hook for the persona key without dragging the whole settings
 * machinery into the article-detail page (or anywhere else that just needs
 * the default register for a planner call).
 *
 * Returns the persona once the fetch completes; falls back to
 * `general_business` while loading or on failure.
 */
export function useDefaultPersona(): AudiencePersona {
  const [persona, setPersona] = useState<AudiencePersona>(DEFAULT);

  useEffect(() => {
    let cancelled = false;
    fetchGeneralConfig()
      .then((cfg: ApiGeneralConfig) => {
        if (cancelled) return;
        const next = cfg.default_audience_persona;
        if (typeof next === "string" && next) {
          setPersona(next as AudiencePersona);
        }
      })
      .catch(() => {
        // Non-fatal — fall back to the default already set.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return persona;
}
