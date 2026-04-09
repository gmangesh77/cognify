"use client";

import { Database, FileText, Box } from "lucide-react";
import { useKnowledgeBaseStats } from "@/hooks/use-metrics";

export function KnowledgeBaseStub() {
  const { data, isLoading } = useKnowledgeBaseStats();

  const sessions = data?.total_sessions ?? 0;
  const sources = data?.total_sources ?? 0;
  const embeddings = data?.total_embeddings ?? 0;

  return (
    <div className="flex items-center gap-6 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
      <div className="flex items-center gap-2">
        <Database className="h-4 w-4 text-neutral-400" />
        <div>
          <p className="text-sm font-medium text-neutral-700">
            {isLoading ? "—" : sessions}
          </p>
          <p className="text-xs text-neutral-400">Sessions</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <FileText className="h-4 w-4 text-neutral-400" />
        <div>
          <p className="text-sm font-medium text-neutral-700">
            {isLoading ? "—" : sources}
          </p>
          <p className="text-xs text-neutral-400">Sources</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Box className="h-4 w-4 text-neutral-400" />
        <div>
          <p className="text-sm font-medium text-neutral-700">
            {isLoading ? "—" : embeddings}
          </p>
          <p className="text-xs text-neutral-400">Embeddings</p>
        </div>
      </div>
    </div>
  );
}
