export type DomainName = "cybersecurity" | "ai-ml" | "cloud" | "devops";

export const DOMAIN_COLORS: Record<string, string> = {
  cybersecurity: "text-domain-cybersecurity",
  "ai-ml": "text-domain-ai-ml",
  cloud: "text-domain-cloud",
  devops: "text-domain-devops",
};

export const DOMAIN_LABELS: Record<string, string> = {
  cybersecurity: "Cybersecurity",
  "ai-ml": "AI / ML",
  cloud: "Cloud",
  devops: "DevOps",
};

export function getDomainColor(domain: string): string {
  return DOMAIN_COLORS[domain] ?? "text-domain-default";
}

export function getDomainLabel(domain: string): string {
  return DOMAIN_LABELS[domain] ?? domain;
}

export const DOMAIN_KEYWORDS: Record<DomainName, string[]> = {
  cybersecurity: ["cybersecurity", "security", "infosec", "threat", "vulnerability"],
  "ai-ml": ["artificial intelligence", "machine learning", "deep learning", "AI", "ML"],
  cloud: ["cloud computing", "AWS", "Azure", "GCP", "kubernetes"],
  devops: ["devops", "CI/CD", "infrastructure", "deployment", "SRE"],
};
