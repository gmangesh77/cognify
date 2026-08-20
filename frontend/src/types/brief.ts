import type { ContentTone, StructuralDiagramMode } from "@/types/api";

export type LengthTarget = "short" | "medium" | "long" | "pillar";

export type BriefContentType = "article" | "how-to" | "analysis" | "report";

export interface BriefFields {
  name: string;
  title?: string | null;
  description?: string | null;
  target_audience?: string | null;
  content_tone?: ContentTone | null;
  preferred_angle?: string | null;
  keywords: string[];
  content_type: BriefContentType;
  length_target: LengthTarget;
  structural_diagram_mode: StructuralDiagramMode;
  audience_persona?: string | null;
  require_outline_approval: boolean;
}

export type BriefCreate = BriefFields;

export type BriefUpdate = Partial<BriefFields>;

export interface Brief extends BriefFields {
  id: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
}
