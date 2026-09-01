export interface PromptView {
  key: string;
  step: string;
  description: string;
  variables: string[];
  default_template: string;
  template: string;
  is_overridden: boolean;
  updated_by: string | null;
  updated_at: string | null;
}
