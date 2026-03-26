import { useState, useCallback, useEffect } from "react";
import type { RankedTopic, ScanState } from "@/types/api";
import { fetchTrends, rankTopics, persistTopics, fetchPersistedTopics } from "@/lib/api/trends";
import type { BackendRankedTopic, PersistedTopic } from "@/lib/api/trends";
import { DOMAIN_KEYWORDS } from "@/types/domain";
import type { DomainName } from "@/types/domain";

/** Dynamic keyword map fetched from settings API. Overrides DOMAIN_KEYWORDS when provided. */
export type DomainKeywordsMap = Record<string, string[]>;

const INITIAL_SCAN: ScanState = {
  isScanning: false,
  completedSources: 0,
  totalSources: 5,
  failedSources: [],
};

function deriveTrendStatus(topic: RankedTopic): RankedTopic["trend_status"] {
  const hoursAgo = (Date.now() - new Date(topic.discovered_at).getTime()) / 3600000;
  if (topic.velocity >= 50 && topic.composite_score >= 80) return "trending";
  if (topic.velocity >= 30) return "rising";
  if (hoursAgo <= 24) return "new";
  return "steady";
}

function toRankedTopic(backend: BackendRankedTopic, domain: string): RankedTopic {
  const partial: RankedTopic = {
    title: backend.title,
    description: backend.description,
    source: backend.source,
    external_url: backend.external_url,
    trend_score: backend.trend_score,
    discovered_at: backend.discovered_at,
    velocity: backend.velocity,
    domain_keywords: backend.domain_keywords,
    composite_score: backend.composite_score,
    rank: backend.rank,
    source_count: backend.source_count,
    domain,
    trend_status: "steady",
  };
  return { ...partial, trend_status: deriveTrendStatus(partial) };
}

function fromPersisted(t: PersistedTopic): RankedTopic {
  const partial: RankedTopic = {
    id: t.id,
    title: t.title,
    description: t.description,
    source: t.source,
    external_url: t.external_url,
    trend_score: t.trend_score,
    discovered_at: t.discovered_at,
    velocity: t.velocity,
    domain_keywords: [],
    composite_score: t.composite_score ?? t.trend_score,
    rank: t.rank ?? 0,
    source_count: t.source_count,
    domain: t.domain,
    trend_status: "steady",
  };
  return { ...partial, trend_status: deriveTrendStatus(partial) };
}

export function useScanTopics(dynamicKeywords?: DomainKeywordsMap) {
  const [topics, setTopics] = useState<RankedTopic[]>([]);
  const [scanState, setScanState] = useState<ScanState>(INITIAL_SCAN);

  // Load persisted topics on mount
  useEffect(() => {
    async function loadPersisted() {
      try {
        const result = await fetchPersistedTopics("", 1, 50);
        if (result.items.length > 0) {
          setTopics(result.items.map(fromPersisted));
        }
      } catch {
        // API unavailable — stay empty
      }
    }
    loadPersisted();
  }, []);

  const startScan = useCallback(async (domain: string) => {
    setScanState({ ...INITIAL_SCAN, isScanning: true });
    setTopics([]);

    // Step 1: Fetch raw trends from all sources
    // Use dynamicKeywords from settings API when available; fall back to hardcoded DOMAIN_KEYWORDS
    const keywordMap = dynamicKeywords ?? DOMAIN_KEYWORDS;
    const keywords = (keywordMap as Record<string, string[]>)[domain] ?? DOMAIN_KEYWORDS[domain as DomainName] ?? [domain];
    const fetchResult = await fetchTrends({
      domain_keywords: keywords,
      max_results: 50,
    });

    const sourcesQueried = fetchResult.sources_queried.length;
    setScanState((s) => ({
      ...s,
      totalSources: sourcesQueried || INITIAL_SCAN.totalSources,
      completedSources: sourcesQueried || INITIAL_SCAN.totalSources,
    }));

    // Step 2: Rank and deduplicate
    const rankResult = await rankTopics({
      topics: fetchResult.topics,
      domain,
      domain_keywords: keywords,
    });

    let ranked = rankResult.ranked_topics.map((t) => toRankedTopic(t, domain));

    // Step 3: Persist to database and get topic IDs
    try {
      const persistResult = await persistTopics({
        ranked_topics: rankResult.ranked_topics,
        domain,
      });
      // Attach DB IDs to frontend topics for Generate Article
      if (persistResult.topic_ids.length === ranked.length) {
        ranked = ranked.map((t, i) => ({ ...t, id: persistResult.topic_ids[i] }));
      }
    } catch {
      console.warn("Topic persistence failed — results shown but not saved");
    }

    setTopics(ranked);
    setScanState((s) => ({ ...s, isScanning: false }));
  }, [dynamicKeywords]);

  return { topics, scanState, startScan };
}
