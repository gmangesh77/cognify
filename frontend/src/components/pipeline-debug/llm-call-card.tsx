"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronRight, AlertCircle } from "lucide-react";
import type { LlmCallResponse } from "@/types/pipeline-debug";

interface LlmCallCardProps {
  call: LlmCallResponse;
}

export function LlmCallCard({ call }: LlmCallCardProps) {
  const [showPrompt, setShowPrompt] = useState(false);
  const [showResponse, setShowResponse] = useState(false);

  return (
    <div className="rounded-md border border-neutral-100 bg-neutral-50 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {call.error && <AlertCircle className="h-3.5 w-3.5 text-red-500" />}
          <span className="text-xs font-medium text-neutral-700">
            {call.model_name}
          </span>
          <span className="text-xs text-neutral-400">·</span>
          <span className="text-xs text-neutral-500">
            {call.duration_ms != null ? `${call.duration_ms}ms` : "—"}
          </span>
          {(call.input_tokens || call.output_tokens) && (
            <>
              <span className="text-xs text-neutral-400">·</span>
              <span className="text-xs text-neutral-500">
                {call.input_tokens ?? 0} → {call.output_tokens ?? 0} tokens
              </span>
            </>
          )}
        </div>
      </div>

      {call.error && (
        <p className="mt-2 text-xs text-red-600">{call.error}</p>
      )}

      <div className="mt-2 flex gap-2">
        <ToggleButton
          label="Prompt"
          count={call.prompt_messages.length}
          open={showPrompt}
          onClick={() => setShowPrompt((v) => !v)}
        />
        <ToggleButton
          label="Response"
          open={showResponse}
          onClick={() => setShowResponse((v) => !v)}
        />
      </div>

      {showPrompt && (
        <div className="mt-2 space-y-2">
          {call.prompt_messages.map((msg, i) => (
            <div key={i} className="rounded border border-neutral-200 bg-white p-2">
              <p className="mb-1 text-xs font-medium uppercase text-neutral-400">
                {msg.role}
              </p>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-neutral-700">
                {msg.content}
              </pre>
            </div>
          ))}
        </div>
      )}

      {showResponse && (
        <div className="mt-2 rounded border border-neutral-200 bg-white p-2">
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-neutral-700">
            {call.response_content || "(empty)"}
          </pre>
        </div>
      )}
    </div>
  );
}

function ToggleButton({
  label,
  count,
  open,
  onClick,
}: {
  label: string;
  count?: number;
  open: boolean;
  onClick: () => void;
}) {
  const Icon = open ? ChevronDown : ChevronRight;
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium transition-colors",
        open
          ? "bg-primary-light text-primary"
          : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200",
      )}
    >
      <Icon className="h-3 w-3" />
      {label}
      {count != null && <span className="text-neutral-400">({count})</span>}
    </button>
  );
}
