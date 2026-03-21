import { Database, FileText, Box } from "lucide-react";
import type { ResearchSessionSummary } from "@/types/research";

interface KnowledgeBaseStatsProps {
  sessions: ResearchSessionSummary[];
}

export function KnowledgeBaseStub({ sessions }: KnowledgeBaseStatsProps) {
  const totalSources = sessions.reduce((sum, s) => sum + s.sources_count, 0);
  const totalEmbeddings = sessions.reduce(
    (sum, s) => sum + s.embeddings_count,
    0,
  );
  const completedSessions = sessions.filter(
    (s) => s.status === "complete",
  ).length;

  return (
    <div className="flex items-center gap-6 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
      <div className="flex items-center gap-2">
        <Database className="h-4 w-4 text-neutral-400" />
        <div>
          <p className="text-sm font-medium text-neutral-700">
            {completedSessions}
          </p>
          <p className="text-xs text-neutral-400">Sessions</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <FileText className="h-4 w-4 text-neutral-400" />
        <div>
          <p className="text-sm font-medium text-neutral-700">{totalSources}</p>
          <p className="text-xs text-neutral-400">Sources</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Box className="h-4 w-4 text-neutral-400" />
        <div>
          <p className="text-sm font-medium text-neutral-700">
            {totalEmbeddings}
          </p>
          <p className="text-xs text-neutral-400">Embeddings</p>
        </div>
      </div>
    </div>
  );
}
