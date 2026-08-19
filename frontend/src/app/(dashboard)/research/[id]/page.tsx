"use client";

import { useParams } from "next/navigation";
import { Header } from "@/components/layout/header";
import { SessionProgress } from "@/components/research/session-progress";

export default function ResearchSessionPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="flex flex-col gap-6">
      <Header title="Article generation" subtitle="Live progress for this research session" />
      <SessionProgress sessionId={id} />
    </div>
  );
}
