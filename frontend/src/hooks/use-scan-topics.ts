import { useState, useCallback } from "react";
import type { RankedTopic, ScanState } from "@/types/api";
import { mockTopics } from "@/lib/mock/topics";
import { SOURCE_NAMES } from "@/types/sources";

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

export function useScanTopics() {
  const [topics, setTopics] = useState<RankedTopic[]>([]);
  const [scanState, setScanState] = useState<ScanState>(INITIAL_SCAN);

  const startScan = useCallback((domain: string) => {
    setScanState({ ...INITIAL_SCAN, isScanning: true });
    setTopics([]);

    let completed = 0;
    const total = SOURCE_NAMES.length;

    SOURCE_NAMES.forEach((_, i) => {
      setTimeout(() => {
        completed += 1;
        setScanState((s) => ({ ...s, completedSources: s.completedSources + 1 }));

        if (completed === total) {
          const filtered = mockTopics
            .filter((t) => t.domain === domain || domain === "")
            .map((t) => ({ ...t, trend_status: deriveTrendStatus(t) }));
          setTopics(filtered);
          setScanState((s) => ({ ...s, isScanning: false }));
        }
      }, (i + 1) * 400);
    });
  }, []);

  return { topics, scanState, startScan };
}
