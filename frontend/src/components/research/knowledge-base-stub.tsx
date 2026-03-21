import { Database } from "lucide-react";

export function KnowledgeBaseStub() {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-dashed border-neutral-300 bg-neutral-50 p-4">
      <Database className="h-5 w-5 text-neutral-400" />
      <div>
        <p className="text-sm font-medium text-neutral-600">Knowledge Base</p>
        <p className="text-xs text-neutral-400">Stats and data source connectors coming in a future update.</p>
      </div>
    </div>
  );
}
