# DASH-005: Settings & Configuration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Settings page placeholder with a fully functional 5-tab settings screen (Domains, LLM Config, API Keys, SEO Defaults, General) using mock data.

**Architecture:** Single `/settings` page with client-side tab state. A `useSettings` hook manages all settings CRUD via local `useState` (no backend API yet). Each tab is a focused component receiving 2-3 props max. Modals follow the `GenerateArticleModal` overlay pattern from DASH-002.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind v4, Vitest, React Testing Library

**Spec:** `docs/superpowers/specs/2026-03-20-dash-005-settings-configuration-design.md`

**Baseline:** 91 frontend tests passing across 22 test files.

**Worktree:** `D:/Workbench/github/cognify-dash-005` on branch `feature/DASH-005-settings-configuration`

---

## File Structure

### New Files

| File | Responsibility | ~Lines |
|------|---------------|--------|
| `frontend/src/types/settings.ts` | All settings type definitions | ~55 |
| `frontend/src/lib/mock/settings.ts` | Mock data + constants (API_KEY_SERVICES) | ~65 |
| `frontend/src/components/ui/switch.tsx` | Toggle switch UI primitive | ~25 |
| `frontend/src/hooks/use-settings.ts` | All settings state + CRUD actions | ~85 |
| `frontend/src/hooks/use-settings.test.ts` | Hook tests | ~120 |
| `frontend/src/components/settings/settings-nav.tsx` | Left tab navigation | ~40 |
| `frontend/src/components/settings/settings-nav.test.tsx` | Nav tests | ~35 |
| `frontend/src/components/settings/domain-card.tsx` | Single domain display card | ~55 |
| `frontend/src/components/settings/domain-card.test.tsx` | Card tests | ~45 |
| `frontend/src/components/settings/domain-modal.tsx` | Add/Edit domain form modal | ~95 |
| `frontend/src/components/settings/domain-modal.test.tsx` | Modal tests | ~90 |
| `frontend/src/components/settings/domains-tab.tsx` | Domain list + add button | ~50 |
| `frontend/src/components/settings/domains-tab.test.tsx` | Tab tests | ~55 |
| `frontend/src/components/settings/llm-config-tab.tsx` | 3 model dropdowns | ~55 |
| `frontend/src/components/settings/llm-config-tab.test.tsx` | Tab tests | ~40 |
| `frontend/src/components/settings/api-key-row.tsx` | Single API key row display | ~55 |
| `frontend/src/components/settings/api-key-row.test.tsx` | Row tests | ~50 |
| `frontend/src/components/settings/api-key-modal.tsx` | Add API key form modal | ~65 |
| `frontend/src/components/settings/api-key-modal.test.tsx` | Modal tests | ~55 |
| `frontend/src/components/settings/api-keys-tab.tsx` | Key list + add button | ~50 |
| `frontend/src/components/settings/api-keys-tab.test.tsx` | Tab tests | ~50 |
| `frontend/src/components/settings/seo-defaults-tab.tsx` | 5 toggle switches | ~65 |
| `frontend/src/components/settings/seo-defaults-tab.test.tsx` | Tab tests | ~50 |
| `frontend/src/components/settings/general-tab.tsx` | 2 config dropdowns | ~50 |
| `frontend/src/components/settings/general-tab.test.tsx` | Tab tests | ~40 |

### Modified Files

| File | Change |
|------|--------|
| `frontend/src/app/(dashboard)/settings/page.tsx` | Replace placeholder with full settings page (~65 lines) |

---

## Task 1: Types and Mock Data

**Files:**
- Create: `frontend/src/types/settings.ts`
- Create: `frontend/src/lib/mock/settings.ts`

- [ ] **Step 1: Create settings type definitions**

Create `frontend/src/types/settings.ts`:

```typescript
import type { SourceName } from "./sources";

export type SettingsTab = "domains" | "llm" | "api-keys" | "seo" | "general";

// --- Domain ---

export interface DomainConfig {
  id: string;
  name: string;
  status: "active" | "inactive";
  trendSources: SourceName[];
  keywords: string[];
  articleCount: number;
}

// --- API Keys ---

export type ApiKeyService = "anthropic" | "serpapi" | "ghost" | "newsapi" | "arxiv";

export interface ApiKeyConfig {
  id: string;
  service: ApiKeyService;
  maskedKey: string;
  status: "active" | "inactive";
}

// --- LLM ---

export type PrimaryModel = "claude-opus-4" | "claude-sonnet-4" | "gpt-4o";
export type DraftingModel = "claude-sonnet-4" | "claude-opus-4" | "gpt-4o-mini";
export type ImageModel = "stable-diffusion-xl" | "dall-e-3" | "midjourney";

export interface LlmConfig {
  primaryModel: PrimaryModel;
  draftingModel: DraftingModel;
  imageGeneration: ImageModel;
}

// --- SEO ---

export interface SeoDefaults {
  autoMetaTags: boolean;
  keywordOptimization: boolean;
  autoCoverImages: boolean;
  includeCitations: boolean;
  humanReviewBeforePublish: boolean;
}

// --- General ---

export type ArticleLength = "1000-2000" | "3000-5000" | "5000-8000";
export type ContentTone = "professional" | "casual" | "technical" | "educational";

export interface GeneralConfig {
  articleLengthTarget: ArticleLength;
  contentTone: ContentTone;
}
```

- [ ] **Step 2: Create mock data and constants**

Create `frontend/src/lib/mock/settings.ts`:

```typescript
import type {
  DomainConfig,
  ApiKeyConfig,
  ApiKeyService,
  LlmConfig,
  SeoDefaults,
  GeneralConfig,
} from "@/types/settings";

export const API_KEY_SERVICES: { value: ApiKeyService; label: string }[] = [
  { value: "anthropic", label: "Anthropic API" },
  { value: "serpapi", label: "SerpAPI" },
  { value: "ghost", label: "Ghost Admin" },
  { value: "newsapi", label: "NewsAPI" },
  { value: "arxiv", label: "arXiv" },
];

export const mockDomains: DomainConfig[] = [
  {
    id: "dom-1",
    name: "Cybersecurity",
    status: "active",
    trendSources: ["google_trends", "reddit", "hackernews"],
    keywords: ["security", "threats", "CVE"],
    articleCount: 24,
  },
  {
    id: "dom-2",
    name: "AI & Machine Learning",
    status: "inactive",
    trendSources: ["arxiv", "hackernews", "reddit"],
    keywords: ["LLM", "Transformers", "GPT"],
    articleCount: 7,
  },
];

export const mockApiKeys: ApiKeyConfig[] = [
  { id: "key-1", service: "anthropic", maskedKey: "sk-ant-••••••••7f3a", status: "active" },
  { id: "key-2", service: "serpapi", maskedKey: "serp-••••••••2b1c", status: "active" },
  { id: "key-3", service: "ghost", maskedKey: "ghost-••••••••9d4e", status: "active" },
  { id: "key-4", service: "newsapi", maskedKey: "news-••••••••4a8f", status: "active" },
];

export const mockLlmConfig: LlmConfig = {
  primaryModel: "claude-opus-4",
  draftingModel: "claude-sonnet-4",
  imageGeneration: "stable-diffusion-xl",
};

export const mockSeoDefaults: SeoDefaults = {
  autoMetaTags: true,
  keywordOptimization: true,
  autoCoverImages: true,
  includeCitations: true,
  humanReviewBeforePublish: true,
};

export const mockGeneralConfig: GeneralConfig = {
  articleLengthTarget: "3000-5000",
  contentTone: "professional",
};
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors related to settings types.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/settings.ts frontend/src/lib/mock/settings.ts
git commit -m "feat(dash-005): add settings types and mock data"
```

---

## Task 2: Switch UI Component

**Files:**
- Create: `frontend/src/components/ui/switch.tsx`

- [ ] **Step 1: Create the Switch component**

Create `frontend/src/components/ui/switch.tsx`. Follow the `Input` component pattern — a thin wrapper with Tailwind styles:

```typescript
import { cn } from "@/lib/utils";

interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  id?: string;
}

export function Switch({ checked, onCheckedChange, id }: SwitchProps) {
  return (
    <button
      id={id}
      role="switch"
      type="button"
      aria-checked={checked}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
        checked ? "bg-primary" : "bg-neutral-200"
      )}
    >
      <span
        className={cn(
          "pointer-events-none block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform",
          checked ? "translate-x-5" : "translate-x-0"
        )}
      />
    </button>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -10`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/switch.tsx
git commit -m "feat(dash-005): add Switch toggle component"
```

---

## Task 3: useSettings Hook

**Files:**
- Create: `frontend/src/hooks/use-settings.ts`
- Create: `frontend/src/hooks/use-settings.test.ts`

- [ ] **Step 1: Write failing tests for useSettings**

Create `frontend/src/hooks/use-settings.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSettings } from "./use-settings";

describe("useSettings", () => {
  it("initializes with mock domains", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.domains).toHaveLength(2);
    expect(result.current.domains[0].name).toBe("Cybersecurity");
  });

  it("initializes with mock LLM config", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.llmConfig.primaryModel).toBe("claude-opus-4");
  });

  it("initializes with mock API keys", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.apiKeys).toHaveLength(4);
  });

  it("initializes with mock SEO defaults", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.seoDefaults.autoMetaTags).toBe(true);
  });

  it("initializes with mock general config", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.generalConfig.contentTone).toBe("professional");
  });

  // --- Domain CRUD ---

  it("adds a domain", () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.addDomain({
        name: "Cloud Computing",
        status: "active",
        trendSources: ["hackernews"],
        keywords: ["AWS", "Azure"],
      });
    });
    expect(result.current.domains).toHaveLength(3);
    expect(result.current.domains[2].name).toBe("Cloud Computing");
    expect(result.current.domains[2].articleCount).toBe(0);
  });

  it("updates a domain", () => {
    const { result } = renderHook(() => useSettings());
    const id = result.current.domains[0].id;
    act(() => {
      result.current.updateDomain(id, { name: "InfoSec" });
    });
    expect(result.current.domains[0].name).toBe("InfoSec");
  });

  it("deletes a domain", () => {
    const { result } = renderHook(() => useSettings());
    const id = result.current.domains[1].id;
    act(() => {
      result.current.deleteDomain(id);
    });
    expect(result.current.domains).toHaveLength(1);
  });

  // --- LLM Config ---

  it("updates LLM config", () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.updateLlmConfig({ primaryModel: "claude-sonnet-4" });
    });
    expect(result.current.llmConfig.primaryModel).toBe("claude-sonnet-4");
  });

  // --- API Keys ---

  it("adds an API key", () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.addApiKey("arxiv", "arxiv-key-123");
    });
    expect(result.current.apiKeys).toHaveLength(5);
    expect(result.current.apiKeys[4].service).toBe("arxiv");
    expect(result.current.apiKeys[4].maskedKey).toContain("••••");
  });

  it("rotates an API key", () => {
    const { result } = renderHook(() => useSettings());
    const id = result.current.apiKeys[0].id;
    act(() => {
      result.current.rotateApiKey(id, "new-key-456");
    });
    expect(result.current.apiKeys[0].maskedKey).toContain("••••");
    expect(result.current.apiKeys[0].maskedKey).not.toBe("sk-ant-••••••••7f3a");
  });

  // --- SEO Defaults ---

  it("toggles a SEO default", () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.toggleSeoDefault("autoMetaTags");
    });
    expect(result.current.seoDefaults.autoMetaTags).toBe(false);
  });

  // --- General Config ---

  it("updates general config", () => {
    const { result } = renderHook(() => useSettings());
    act(() => {
      result.current.updateGeneralConfig({ contentTone: "casual" });
    });
    expect(result.current.generalConfig.contentTone).toBe("casual");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/hooks/use-settings.test.ts 2>&1 | tail -10`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement useSettings hook**

Create `frontend/src/hooks/use-settings.ts`:

```typescript
import { useState, useCallback } from "react";
import type {
  DomainConfig,
  LlmConfig,
  ApiKeyConfig,
  ApiKeyService,
  SeoDefaults,
  GeneralConfig,
} from "@/types/settings";
import {
  mockDomains,
  mockLlmConfig,
  mockApiKeys,
  mockSeoDefaults,
  mockGeneralConfig,
} from "@/lib/mock/settings";

function maskKey(key: string): string {
  const prefix = key.slice(0, 4);
  const suffix = key.slice(-4);
  return `${prefix}-••••••••${suffix}`;
}

export function useSettings() {
  const [domains, setDomains] = useState<DomainConfig[]>(mockDomains);
  const [llmConfig, setLlmConfig] = useState<LlmConfig>(mockLlmConfig);
  const [apiKeys, setApiKeys] = useState<ApiKeyConfig[]>(mockApiKeys);
  const [seoDefaults, setSeoDefaults] = useState<SeoDefaults>(mockSeoDefaults);
  const [generalConfig, setGeneralConfig] = useState<GeneralConfig>(mockGeneralConfig);

  const addDomain = useCallback(
    (data: Omit<DomainConfig, "id" | "articleCount">) => {
      const newDomain: DomainConfig = {
        ...data,
        id: `dom-${Date.now()}`,
        articleCount: 0,
      };
      setDomains((prev) => [...prev, newDomain]);
    },
    [],
  );

  const updateDomain = useCallback(
    (id: string, updates: Partial<DomainConfig>) => {
      setDomains((prev) =>
        prev.map((d) => (d.id === id ? { ...d, ...updates } : d)),
      );
    },
    [],
  );

  const deleteDomain = useCallback((id: string) => {
    setDomains((prev) => prev.filter((d) => d.id !== id));
  }, []);

  const updateLlmConfig = useCallback(
    (updates: Partial<LlmConfig>) => {
      setLlmConfig((prev) => ({ ...prev, ...updates }));
    },
    [],
  );

  const addApiKey = useCallback(
    (service: ApiKeyService, key: string) => {
      const newKey: ApiKeyConfig = {
        id: `key-${Date.now()}`,
        service,
        maskedKey: maskKey(key),
        status: "active",
      };
      setApiKeys((prev) => [...prev, newKey]);
    },
    [],
  );

  const rotateApiKey = useCallback(
    (id: string, newKey: string) => {
      setApiKeys((prev) =>
        prev.map((k) =>
          k.id === id ? { ...k, maskedKey: maskKey(newKey) } : k,
        ),
      );
    },
    [],
  );

  const toggleSeoDefault = useCallback(
    (key: keyof SeoDefaults) => {
      setSeoDefaults((prev) => ({ ...prev, [key]: !prev[key] }));
    },
    [],
  );

  const updateGeneralConfig = useCallback(
    (updates: Partial<GeneralConfig>) => {
      setGeneralConfig((prev) => ({ ...prev, ...updates }));
    },
    [],
  );

  return {
    domains,
    llmConfig,
    apiKeys,
    seoDefaults,
    generalConfig,
    addDomain,
    updateDomain,
    deleteDomain,
    updateLlmConfig,
    addApiKey,
    rotateApiKey,
    toggleSeoDefault,
    updateGeneralConfig,
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/hooks/use-settings.test.ts 2>&1 | tail -10`
Expected: 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/use-settings.ts frontend/src/hooks/use-settings.test.ts
git commit -m "feat(dash-005): add useSettings hook with CRUD actions"
```

---

## Task 4: SettingsNav Component

**Files:**
- Create: `frontend/src/components/settings/settings-nav.tsx`
- Create: `frontend/src/components/settings/settings-nav.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/settings/settings-nav.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SettingsNav } from "./settings-nav";

describe("SettingsNav", () => {
  it("renders all 5 tab items", () => {
    render(<SettingsNav activeTab="domains" onTabChange={vi.fn()} />);
    expect(screen.getByText("Domains")).toBeInTheDocument();
    expect(screen.getByText("LLM Configuration")).toBeInTheDocument();
    expect(screen.getByText("API Keys")).toBeInTheDocument();
    expect(screen.getByText("SEO Defaults")).toBeInTheDocument();
    expect(screen.getByText("General")).toBeInTheDocument();
  });

  it("highlights the active tab", () => {
    render(<SettingsNav activeTab="llm" onTabChange={vi.fn()} />);
    const activeButton = screen.getByText("LLM Configuration");
    expect(activeButton.closest("button")).toHaveClass("bg-primary/10");
  });

  it("calls onTabChange when a tab is clicked", () => {
    const handler = vi.fn();
    render(<SettingsNav activeTab="domains" onTabChange={handler} />);
    fireEvent.click(screen.getByText("API Keys"));
    expect(handler).toHaveBeenCalledWith("api-keys");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/settings/settings-nav.test.tsx 2>&1 | tail -10`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement SettingsNav**

Create `frontend/src/components/settings/settings-nav.tsx`:

```typescript
import { Globe, Cpu, Key, Search, Sliders } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SettingsTab } from "@/types/settings";

const TABS: { key: SettingsTab; label: string; icon: React.ElementType }[] = [
  { key: "domains", label: "Domains", icon: Globe },
  { key: "llm", label: "LLM Configuration", icon: Cpu },
  { key: "api-keys", label: "API Keys", icon: Key },
  { key: "seo", label: "SEO Defaults", icon: Search },
  { key: "general", label: "General", icon: Sliders },
];

interface SettingsNavProps {
  activeTab: SettingsTab;
  onTabChange: (tab: SettingsTab) => void;
}

export function SettingsNav({ activeTab, onTabChange }: SettingsNavProps) {
  return (
    <nav className="w-52 shrink-0 space-y-1 border-r border-neutral-200 bg-neutral-50 p-3">
      {TABS.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          onClick={() => onTabChange(key)}
          className={cn(
            "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            activeTab === key
              ? "bg-primary/10 text-primary"
              : "text-neutral-600 hover:bg-neutral-100"
          )}
        >
          <Icon className="h-4 w-4" />
          {label}
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/settings-nav.test.tsx 2>&1 | tail -10`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/settings-nav.tsx frontend/src/components/settings/settings-nav.test.tsx
git commit -m "feat(dash-005): add SettingsNav tab component"
```

---

## Task 5: DomainCard Component

**Files:**
- Create: `frontend/src/components/settings/domain-card.tsx`
- Create: `frontend/src/components/settings/domain-card.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/settings/domain-card.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DomainCard } from "./domain-card";
import type { DomainConfig } from "@/types/settings";

const mockDomain: DomainConfig = {
  id: "dom-1",
  name: "Cybersecurity",
  status: "active",
  trendSources: ["google_trends", "reddit", "hackernews"],
  keywords: ["security", "threats", "CVE"],
  articleCount: 24,
};

describe("DomainCard", () => {
  it("renders domain name", () => {
    render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
  });

  it("renders status badge", () => {
    render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders trend source count", () => {
    render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(screen.getByText("3 sources")).toBeInTheDocument();
  });

  it("renders keyword count", () => {
    render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(screen.getByText("3 keywords")).toBeInTheDocument();
  });

  it("renders article count", () => {
    render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(screen.getByText("24 articles")).toBeInTheDocument();
  });

  it("applies active border styling", () => {
    const { container } = render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(container.firstChild).toHaveClass("border-primary");
  });

  it("calls onEdit when Edit is clicked", () => {
    const handler = vi.fn();
    render(<DomainCard domain={mockDomain} onEdit={handler} />);
    fireEvent.click(screen.getByText("Edit"));
    expect(handler).toHaveBeenCalledWith(mockDomain);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/settings/domain-card.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement DomainCard**

Create `frontend/src/components/settings/domain-card.tsx`:

```typescript
import { cn } from "@/lib/utils";
import type { DomainConfig } from "@/types/settings";

interface DomainCardProps {
  domain: DomainConfig;
  onEdit: (domain: DomainConfig) => void;
}

export function DomainCard({ domain, onEdit }: DomainCardProps) {
  const isActive = domain.status === "active";

  return (
    <div
      className={cn(
        "rounded-lg border p-4 shadow-sm",
        isActive ? "border-primary border-2" : "border-neutral-200"
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-heading text-base font-semibold text-neutral-900">
            {domain.name}
          </h3>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-medium",
              isActive
                ? "bg-success/10 text-success"
                : "bg-neutral-100 text-neutral-500"
            )}
          >
            {isActive ? "Active" : "Inactive"}
          </span>
        </div>
        <button
          onClick={() => onEdit(domain)}
          className="text-sm font-medium text-primary hover:underline"
        >
          Edit
        </button>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
        <div>
          <span className="text-xs font-medium uppercase text-neutral-400">
            Trend Sources
          </span>
          <p className="mt-0.5 text-neutral-700">
            {domain.trendSources.length} sources
          </p>
        </div>
        <div>
          <span className="text-xs font-medium uppercase text-neutral-400">
            Keywords
          </span>
          <p className="mt-0.5 text-neutral-700">
            {domain.keywords.length} keywords
          </p>
        </div>
        <div>
          <span className="text-xs font-medium uppercase text-neutral-400">
            Articles
          </span>
          <p className="mt-0.5 text-neutral-700">
            {domain.articleCount} articles
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/domain-card.test.tsx 2>&1 | tail -10`
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/domain-card.tsx frontend/src/components/settings/domain-card.test.tsx
git commit -m "feat(dash-005): add DomainCard component"
```

---

## Task 6: DomainModal Component

**Files:**
- Create: `frontend/src/components/settings/domain-modal.tsx`
- Create: `frontend/src/components/settings/domain-modal.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/settings/domain-modal.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DomainModal } from "./domain-modal";
import type { DomainConfig } from "@/types/settings";

const mockDomain: DomainConfig = {
  id: "dom-1",
  name: "Cybersecurity",
  status: "active",
  trendSources: ["google_trends", "reddit"],
  keywords: ["security", "threats"],
  articleCount: 24,
};

describe("DomainModal", () => {
  it("renders nothing when domain is undefined and open is false", () => {
    const { container } = render(
      <DomainModal domain={null} open={false} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders Add Domain title when domain is null", () => {
    render(<DomainModal domain={null} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByText("Add Domain")).toBeInTheDocument();
  });

  it("renders Edit Domain title when domain is provided", () => {
    render(
      <DomainModal domain={mockDomain} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(screen.getByText("Edit Domain")).toBeInTheDocument();
  });

  it("pre-fills form when editing", () => {
    render(
      <DomainModal domain={mockDomain} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(screen.getByDisplayValue("Cybersecurity")).toBeInTheDocument();
    expect(screen.getByDisplayValue("security, threats")).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", () => {
    const handleClose = vi.fn();
    render(<DomainModal domain={null} open={true} onClose={handleClose} onSubmit={vi.fn()} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(handleClose).toHaveBeenCalled();
  });

  it("calls onSubmit with save action when Save is clicked", () => {
    const handleSubmit = vi.fn();
    render(
      <DomainModal domain={null} open={true} onClose={vi.fn()} onSubmit={handleSubmit} />
    );
    fireEvent.change(screen.getByLabelText("Domain Name"), {
      target: { value: "New Domain" },
    });
    fireEvent.click(screen.getByText("Save Domain"));
    expect(handleSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ type: "save" })
    );
  });

  it("shows delete button only in edit mode", () => {
    const { rerender } = render(
      <DomainModal domain={null} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(screen.queryByText("Delete Domain")).not.toBeInTheDocument();
    rerender(
      <DomainModal domain={mockDomain} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(screen.getByText("Delete Domain")).toBeInTheDocument();
  });

  it("shows confirmation before delete", () => {
    render(
      <DomainModal domain={mockDomain} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    fireEvent.click(screen.getByText("Delete Domain"));
    expect(screen.getByText("Are you sure? This cannot be undone.")).toBeInTheDocument();
  });

  it("calls onSubmit with delete action after confirmation", () => {
    const handleSubmit = vi.fn();
    render(
      <DomainModal domain={mockDomain} open={true} onClose={vi.fn()} onSubmit={handleSubmit} />
    );
    fireEvent.click(screen.getByText("Delete Domain"));
    fireEvent.click(screen.getByText("Confirm Delete"));
    expect(handleSubmit).toHaveBeenCalledWith({ type: "delete", id: "dom-1" });
  });

  it("renders trend source checkboxes", () => {
    render(<DomainModal domain={null} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByLabelText("Google Trends")).toBeInTheDocument();
    expect(screen.getByLabelText("Reddit")).toBeInTheDocument();
    expect(screen.getByLabelText("Hacker News")).toBeInTheDocument();
    expect(screen.getByLabelText("NewsAPI")).toBeInTheDocument();
    expect(screen.getByLabelText("arXiv")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/settings/domain-modal.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement DomainModal**

Create `frontend/src/components/settings/domain-modal.tsx`. Uses the same overlay pattern as `GenerateArticleModal` (fixed inset-0, z-50, bg-black/50, role="dialog", stopPropagation). Manages local form state with `useState`, resets on open via `useEffect`:

```typescript
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SOURCE_NAMES, SOURCE_LABELS } from "@/types/sources";
import type { SourceName } from "@/types/sources";
import type { DomainConfig } from "@/types/settings";

export type DomainModalAction =
  | { type: "save"; data: Omit<DomainConfig, "id" | "articleCount"> }
  | { type: "delete"; id: string };

interface DomainModalProps {
  domain: DomainConfig | null;
  open: boolean;
  onClose: () => void;
  onSubmit: (action: DomainModalAction) => void;
}

export function DomainModal({ domain, open, onClose, onSubmit }: DomainModalProps) {
  const [name, setName] = useState("");
  const [status, setStatus] = useState<"active" | "inactive">("active");
  const [sources, setSources] = useState<SourceName[]>([]);
  const [keywords, setKeywords] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (open) {
      setName(domain?.name ?? "");
      setStatus(domain?.status ?? "active");
      setSources(domain?.trendSources ?? []);
      setKeywords(domain?.keywords.join(", ") ?? "");
      setConfirmDelete(false);
    }
  }, [open, domain]);

  if (!open) return null;

  const isEdit = domain !== null;

  function toggleSource(source: SourceName) {
    setSources((prev) =>
      prev.includes(source)
        ? prev.filter((s) => s !== source)
        : [...prev, source],
    );
  }

  function handleSave() {
    const parsed = keywords
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    onSubmit({ type: "save", data: { name, status, trendSources: sources, keywords: parsed } });
  }

  function handleDelete() {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    onSubmit({ type: "delete", id: domain!.id });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div role="dialog" className="w-full max-w-lg rounded-xl bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <h2 className="font-heading text-lg font-semibold text-neutral-900">
          {isEdit ? "Edit Domain" : "Add Domain"}
        </h2>

        <div className="mt-4 space-y-4">
          <div>
            <label htmlFor="domain-name" className="block text-sm font-medium text-neutral-700">
              Domain Name
            </label>
            <Input id="domain-name" value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
          </div>

          <div>
            <span className="block text-sm font-medium text-neutral-700">Trend Sources</span>
            <div className="mt-1 flex flex-wrap gap-3">
              {SOURCE_NAMES.map((src) => (
                <label key={src} className="flex items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={sources.includes(src)}
                    onChange={() => toggleSource(src)}
                    className="rounded"
                  />
                  {SOURCE_LABELS[src]}
                </label>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="domain-keywords" className="block text-sm font-medium text-neutral-700">
              Keywords
            </label>
            <Input
              id="domain-keywords"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="Comma-separated keywords"
              className="mt-1"
            />
          </div>

          <div>
            <label htmlFor="domain-status" className="block text-sm font-medium text-neutral-700">
              Status
            </label>
            <select
              id="domain-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as "active" | "inactive")}
              className="mt-1 h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>

        {confirmDelete && (
          <p className="mt-3 text-sm text-red-600">Are you sure? This cannot be undone.</p>
        )}

        <div className="mt-6 flex items-center justify-between">
          <div>
            {isEdit && (
              <Button variant="ghost" onClick={handleDelete} className="text-red-600 hover:text-red-700">
                {confirmDelete ? "Confirm Delete" : "Delete Domain"}
              </Button>
            )}
          </div>
          <div className="flex gap-3">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button onClick={handleSave}>Save Domain</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/domain-modal.test.tsx 2>&1 | tail -10`
Expected: 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/domain-modal.tsx frontend/src/components/settings/domain-modal.test.tsx
git commit -m "feat(dash-005): add DomainModal with add/edit/delete"
```

---

## Task 7: DomainsTab Component

**Files:**
- Create: `frontend/src/components/settings/domains-tab.tsx`
- Create: `frontend/src/components/settings/domains-tab.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/settings/domains-tab.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DomainsTab } from "./domains-tab";
import type { DomainConfig } from "@/types/settings";

const mockDomains: DomainConfig[] = [
  {
    id: "dom-1", name: "Cybersecurity", status: "active",
    trendSources: ["google_trends", "reddit"], keywords: ["security"], articleCount: 24,
  },
  {
    id: "dom-2", name: "AI & ML", status: "inactive",
    trendSources: ["arxiv"], keywords: ["LLM"], articleCount: 7,
  },
];

const actions = { add: vi.fn(), update: vi.fn(), delete: vi.fn() };

describe("DomainsTab", () => {
  it("renders all domain cards", () => {
    render(<DomainsTab domains={mockDomains} actions={actions} />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
    expect(screen.getByText("AI & ML")).toBeInTheDocument();
  });

  it("renders Add Domain button", () => {
    render(<DomainsTab domains={mockDomains} actions={actions} />);
    expect(screen.getByText("+ Add Domain")).toBeInTheDocument();
  });

  it("opens add modal when button clicked", () => {
    render(<DomainsTab domains={mockDomains} actions={actions} />);
    fireEvent.click(screen.getByText("+ Add Domain"));
    expect(screen.getByText("Add Domain")).toBeInTheDocument();
  });

  it("opens edit modal when Edit is clicked on a card", () => {
    render(<DomainsTab domains={mockDomains} actions={actions} />);
    fireEvent.click(screen.getAllByText("Edit")[0]);
    expect(screen.getByText("Edit Domain")).toBeInTheDocument();
  });

  it("shows empty state when no domains", () => {
    render(<DomainsTab domains={[]} actions={actions} />);
    expect(screen.getByText("No domains configured")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/settings/domains-tab.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement DomainsTab**

Create `frontend/src/components/settings/domains-tab.tsx`:

```typescript
import { useState } from "react";
import { Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DomainCard } from "./domain-card";
import { DomainModal } from "./domain-modal";
import type { DomainModalAction } from "./domain-modal";
import type { DomainConfig } from "@/types/settings";

interface DomainActions {
  add: (data: Omit<DomainConfig, "id" | "articleCount">) => void;
  update: (id: string, updates: Partial<DomainConfig>) => void;
  delete: (id: string) => void;
}

interface DomainsTabProps {
  domains: DomainConfig[];
  actions: DomainActions;
}

export function DomainsTab({ domains, actions }: DomainsTabProps) {
  const [editDomain, setEditDomain] = useState<DomainConfig | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  function openAdd() {
    setEditDomain(null);
    setModalOpen(true);
  }

  function openEdit(domain: DomainConfig) {
    setEditDomain(domain);
    setModalOpen(true);
  }

  function handleSubmit(action: DomainModalAction) {
    if (action.type === "save") {
      if (editDomain) {
        actions.update(editDomain.id, action.data);
      } else {
        actions.add(action.data);
      }
    } else {
      actions.delete(action.id);
    }
    setModalOpen(false);
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-lg font-semibold text-neutral-900">Domains</h2>
        <Button variant="ghost" size="sm" onClick={openAdd}>
          + Add Domain
        </Button>
      </div>

      {domains.length === 0 ? (
        <div className="mt-8 flex flex-col items-center justify-center py-12 text-center">
          <Globe className="mb-4 h-10 w-10 text-neutral-300" />
          <p className="text-sm text-neutral-500">No domains configured</p>
          <p className="mt-1 text-xs text-neutral-400">Click &ldquo;+ Add Domain&rdquo; to get started.</p>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {domains.map((domain) => (
            <DomainCard key={domain.id} domain={domain} onEdit={openEdit} />
          ))}
        </div>
      )}

      <DomainModal
        domain={editDomain}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/domains-tab.test.tsx 2>&1 | tail -10`
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/domains-tab.tsx frontend/src/components/settings/domains-tab.test.tsx
git commit -m "feat(dash-005): add DomainsTab with card list and modal"
```

---

## Task 8: LlmConfigTab Component

**Files:**
- Create: `frontend/src/components/settings/llm-config-tab.tsx`
- Create: `frontend/src/components/settings/llm-config-tab.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/settings/llm-config-tab.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LlmConfigTab } from "./llm-config-tab";
import type { LlmConfig } from "@/types/settings";

const mockConfig: LlmConfig = {
  primaryModel: "claude-opus-4",
  draftingModel: "claude-sonnet-4",
  imageGeneration: "stable-diffusion-xl",
};

describe("LlmConfigTab", () => {
  it("renders all 3 dropdowns", () => {
    render(<LlmConfigTab config={mockConfig} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText("Primary Model")).toBeInTheDocument();
    expect(screen.getByLabelText("Drafting Model")).toBeInTheDocument();
    expect(screen.getByLabelText("Image Generation")).toBeInTheDocument();
  });

  it("renders description text for each dropdown", () => {
    render(<LlmConfigTab config={mockConfig} onUpdate={vi.fn()} />);
    expect(screen.getByText(/final article synthesis/)).toBeInTheDocument();
    expect(screen.getByText(/section drafting/)).toBeInTheDocument();
    expect(screen.getByText(/hero images/)).toBeInTheDocument();
  });

  it("calls onUpdate when primary model changes", () => {
    const handler = vi.fn();
    render(<LlmConfigTab config={mockConfig} onUpdate={handler} />);
    fireEvent.change(screen.getByLabelText("Primary Model"), {
      target: { value: "claude-sonnet-4" },
    });
    expect(handler).toHaveBeenCalledWith({ primaryModel: "claude-sonnet-4" });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/settings/llm-config-tab.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement LlmConfigTab**

Create `frontend/src/components/settings/llm-config-tab.tsx`:

```typescript
import type { LlmConfig } from "@/types/settings";

interface LlmConfigTabProps {
  config: LlmConfig;
  onUpdate: (updates: Partial<LlmConfig>) => void;
}

const SELECT_CLASS =
  "mt-1 h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm";

export function LlmConfigTab({ config, onUpdate }: LlmConfigTabProps) {
  return (
    <div>
      <h2 className="font-heading text-lg font-semibold text-neutral-900">
        LLM Configuration
      </h2>
      <div className="mt-4 max-w-md space-y-6">
        <div>
          <label htmlFor="primary-model" className="block text-sm font-medium text-neutral-700">
            Primary Model
          </label>
          <select
            id="primary-model"
            value={config.primaryModel}
            onChange={(e) => onUpdate({ primaryModel: e.target.value as LlmConfig["primaryModel"] })}
            className={SELECT_CLASS}
          >
            <option value="claude-opus-4">Claude Opus 4</option>
            <option value="claude-sonnet-4">Claude Sonnet 4</option>
            <option value="gpt-4o">GPT-4o</option>
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Used for final article synthesis and quality pass
          </p>
        </div>

        <div>
          <label htmlFor="drafting-model" className="block text-sm font-medium text-neutral-700">
            Drafting Model
          </label>
          <select
            id="drafting-model"
            value={config.draftingModel}
            onChange={(e) => onUpdate({ draftingModel: e.target.value as LlmConfig["draftingModel"] })}
            className={SELECT_CLASS}
          >
            <option value="claude-sonnet-4">Claude Sonnet 4</option>
            <option value="claude-opus-4">Claude Opus 4</option>
            <option value="gpt-4o-mini">GPT-4o mini</option>
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Used for section drafting and outline generation
          </p>
        </div>

        <div>
          <label htmlFor="image-model" className="block text-sm font-medium text-neutral-700">
            Image Generation
          </label>
          <select
            id="image-model"
            value={config.imageGeneration}
            onChange={(e) => onUpdate({ imageGeneration: e.target.value as LlmConfig["imageGeneration"] })}
            className={SELECT_CLASS}
          >
            <option value="stable-diffusion-xl">Stable Diffusion XL</option>
            <option value="dall-e-3">DALL-E 3</option>
            <option value="midjourney">Midjourney</option>
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Used for article hero images and illustrations
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/llm-config-tab.test.tsx 2>&1 | tail -10`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/llm-config-tab.tsx frontend/src/components/settings/llm-config-tab.test.tsx
git commit -m "feat(dash-005): add LlmConfigTab with model dropdowns"
```

---

## Task 9: ApiKeyRow and ApiKeyModal Components

**Files:**
- Create: `frontend/src/components/settings/api-key-row.tsx`
- Create: `frontend/src/components/settings/api-key-row.test.tsx`
- Create: `frontend/src/components/settings/api-key-modal.tsx`
- Create: `frontend/src/components/settings/api-key-modal.test.tsx`

- [ ] **Step 1: Write failing tests for ApiKeyRow**

Create `frontend/src/components/settings/api-key-row.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ApiKeyRow } from "./api-key-row";
import type { ApiKeyConfig } from "@/types/settings";

const mockKey: ApiKeyConfig = {
  id: "key-1",
  service: "anthropic",
  maskedKey: "sk-ant-••••••••7f3a",
  status: "active",
};

describe("ApiKeyRow", () => {
  it("renders service name", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    expect(screen.getByText("Anthropic API")).toBeInTheDocument();
  });

  it("renders masked key", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    expect(screen.getByText("sk-ant-••••••••7f3a")).toBeInTheDocument();
  });

  it("renders status badge", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows confirmation on first Rotate click", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    fireEvent.click(screen.getByText("Rotate"));
    expect(screen.getByText("Are you sure you want to rotate this key?")).toBeInTheDocument();
  });

  it("shows new key input after confirming rotation", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    fireEvent.click(screen.getByText("Rotate"));
    fireEvent.click(screen.getByText("Confirm"));
    expect(screen.getByPlaceholderText("New API key")).toBeInTheDocument();
  });

  it("calls onRotate with new key after entering it", () => {
    const handler = vi.fn();
    render(<ApiKeyRow apiKey={mockKey} onRotate={handler} />);
    fireEvent.click(screen.getByText("Rotate"));
    fireEvent.click(screen.getByText("Confirm"));
    fireEvent.change(screen.getByPlaceholderText("New API key"), {
      target: { value: "new-key-123" },
    });
    fireEvent.click(screen.getByText("Save"));
    expect(handler).toHaveBeenCalledWith("key-1", "new-key-123");
  });

  it("cancels at confirmation step", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    fireEvent.click(screen.getByText("Rotate"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByText("Are you sure")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write failing tests for ApiKeyModal**

Create `frontend/src/components/settings/api-key-modal.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ApiKeyModal } from "./api-key-modal";

describe("ApiKeyModal", () => {
  it("renders nothing when open is false", () => {
    const { container } = render(
      <ApiKeyModal open={false} onSave={vi.fn()} onClose={vi.fn()} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders form when open", () => {
    render(<ApiKeyModal open={true} onSave={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByText("Add API Key")).toBeInTheDocument();
    expect(screen.getByLabelText("Service")).toBeInTheDocument();
    expect(screen.getByLabelText("API Key")).toBeInTheDocument();
  });

  it("calls onSave with service and key", () => {
    const handleSave = vi.fn();
    render(<ApiKeyModal open={true} onSave={handleSave} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Service"), {
      target: { value: "serpapi" },
    });
    fireEvent.change(screen.getByLabelText("API Key"), {
      target: { value: "serp-my-key" },
    });
    fireEvent.click(screen.getByText("Save"));
    expect(handleSave).toHaveBeenCalledWith("serpapi", "serp-my-key");
  });

  it("calls onClose when Cancel is clicked", () => {
    const handleClose = vi.fn();
    render(<ApiKeyModal open={true} onSave={vi.fn()} onClose={handleClose} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(handleClose).toHaveBeenCalled();
  });

  it("toggles API key visibility", () => {
    render(<ApiKeyModal open={true} onSave={vi.fn()} onClose={vi.fn()} />);
    const keyInput = screen.getByLabelText("API Key");
    expect(keyInput).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByLabelText("Toggle key visibility"));
    expect(keyInput).toHaveAttribute("type", "text");
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/settings/api-key-row.test.tsx src/components/settings/api-key-modal.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 4: Implement ApiKeyRow**

Create `frontend/src/components/settings/api-key-row.tsx`:

```typescript
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_KEY_SERVICES } from "@/lib/mock/settings";
import type { ApiKeyConfig } from "@/types/settings";

type RotateStep = "idle" | "confirm" | "input";

interface ApiKeyRowProps {
  apiKey: ApiKeyConfig;
  onRotate: (id: string, newKey: string) => void;
}

export function ApiKeyRow({ apiKey, onRotate }: ApiKeyRowProps) {
  const [step, setStep] = useState<RotateStep>("idle");
  const [newKey, setNewKey] = useState("");

  const label = API_KEY_SERVICES.find((s) => s.value === apiKey.service)?.label ?? apiKey.service;
  const isActive = apiKey.status === "active";

  function handleSave() {
    onRotate(apiKey.id, newKey);
    setStep("idle");
    setNewKey("");
  }

  function handleCancel() {
    setStep("idle");
    setNewKey("");
  }

  return (
    <div className="border-b border-neutral-100 py-3 last:border-b-0">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-neutral-900">{label}</span>
          <code className="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600">
            {apiKey.maskedKey}
          </code>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-medium",
              isActive ? "bg-success/10 text-success" : "bg-neutral-100 text-neutral-500"
            )}
          >
            {isActive ? "Active" : "Inactive"}
          </span>
        </div>
        {step === "idle" && (
          <Button variant="ghost" size="sm" onClick={() => setStep("confirm")} className="text-primary">
            Rotate
          </Button>
        )}
      </div>
      {step === "confirm" && (
        <div className="mt-2 flex items-center gap-2">
          <p className="text-xs text-neutral-500">Are you sure you want to rotate this key?</p>
          <Button size="sm" onClick={() => setStep("input")}>Confirm</Button>
          <Button variant="ghost" size="sm" onClick={handleCancel}>Cancel</Button>
        </div>
      )}
      {step === "input" && (
        <div className="mt-2 flex items-center gap-2">
          <Input
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="New API key"
            className="max-w-xs"
          />
          <Button size="sm" onClick={handleSave}>Save</Button>
          <Button variant="ghost" size="sm" onClick={handleCancel}>Cancel</Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Implement ApiKeyModal**

Create `frontend/src/components/settings/api-key-modal.tsx`:

```typescript
import { useState, useEffect } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_KEY_SERVICES } from "@/lib/mock/settings";
import type { ApiKeyService } from "@/types/settings";

interface ApiKeyModalProps {
  open: boolean;
  onSave: (service: ApiKeyService, key: string) => void;
  onClose: () => void;
}

export function ApiKeyModal({ open, onSave, onClose }: ApiKeyModalProps) {
  const [service, setService] = useState<ApiKeyService>("anthropic");
  const [key, setKey] = useState("");
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    if (open) {
      setService("anthropic");
      setKey("");
      setShowKey(false);
    }
  }, [open]);

  if (!open) return null;

  function handleSave() {
    onSave(service, key);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div role="dialog" className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <h2 className="font-heading text-lg font-semibold text-neutral-900">Add API Key</h2>
        <div className="mt-4 space-y-4">
          <div>
            <label htmlFor="api-service" className="block text-sm font-medium text-neutral-700">
              Service
            </label>
            <select
              id="api-service"
              value={service}
              onChange={(e) => setService(e.target.value as ApiKeyService)}
              className="mt-1 h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
            >
              {API_KEY_SERVICES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="api-key-value" className="block text-sm font-medium text-neutral-700">
              API Key
            </label>
            <div className="relative mt-1">
              <Input
                id="api-key-value"
                type={showKey ? "text" : "password"}
                value={key}
                onChange={(e) => setKey(e.target.value)}
              />
              <button
                type="button"
                aria-label="Toggle key visibility"
                onClick={() => setShowKey((prev) => !prev)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600"
              >
                {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave}>Save</Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/api-key-row.test.tsx src/components/settings/api-key-modal.test.tsx 2>&1 | tail -10`
Expected: 12 tests PASS (7 ApiKeyRow + 5 ApiKeyModal).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/settings/api-key-row.tsx frontend/src/components/settings/api-key-row.test.tsx frontend/src/components/settings/api-key-modal.tsx frontend/src/components/settings/api-key-modal.test.tsx
git commit -m "feat(dash-005): add ApiKeyRow and ApiKeyModal components"
```

---

## Task 10: ApiKeysTab Component

**Files:**
- Create: `frontend/src/components/settings/api-keys-tab.tsx`
- Create: `frontend/src/components/settings/api-keys-tab.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/settings/api-keys-tab.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ApiKeysTab } from "./api-keys-tab";
import type { ApiKeyConfig, ApiKeyService } from "@/types/settings";

const mockKeys: ApiKeyConfig[] = [
  { id: "key-1", service: "anthropic", maskedKey: "sk-ant-••••7f3a", status: "active" },
  { id: "key-2", service: "serpapi", maskedKey: "serp-••••2b1c", status: "active" },
];

const actions = {
  add: vi.fn() as (service: ApiKeyService, key: string) => void,
  rotate: vi.fn() as (id: string, newKey: string) => void,
};

describe("ApiKeysTab", () => {
  it("renders all key rows", () => {
    render(<ApiKeysTab apiKeys={mockKeys} actions={actions} />);
    expect(screen.getByText("Anthropic API")).toBeInTheDocument();
    expect(screen.getByText("SerpAPI")).toBeInTheDocument();
  });

  it("renders Add API Key button", () => {
    render(<ApiKeysTab apiKeys={mockKeys} actions={actions} />);
    expect(screen.getByText("+ Add API Key")).toBeInTheDocument();
  });

  it("opens add modal when button clicked", () => {
    render(<ApiKeysTab apiKeys={mockKeys} actions={actions} />);
    fireEvent.click(screen.getByText("+ Add API Key"));
    expect(screen.getByText("Add API Key")).toBeInTheDocument();
  });

  it("shows empty state when no keys", () => {
    render(<ApiKeysTab apiKeys={[]} actions={actions} />);
    expect(screen.getByText("No API keys configured")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/settings/api-keys-tab.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement ApiKeysTab**

Create `frontend/src/components/settings/api-keys-tab.tsx`:

```typescript
import { useState } from "react";
import { Key } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiKeyRow } from "./api-key-row";
import { ApiKeyModal } from "./api-key-modal";
import type { ApiKeyConfig, ApiKeyService } from "@/types/settings";

interface KeyActions {
  add: (service: ApiKeyService, key: string) => void;
  rotate: (id: string, newKey: string) => void;
}

interface ApiKeysTabProps {
  apiKeys: ApiKeyConfig[];
  actions: KeyActions;
}

export function ApiKeysTab({ apiKeys, actions }: ApiKeysTabProps) {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-lg font-semibold text-neutral-900">API Keys</h2>
        <Button variant="ghost" size="sm" onClick={() => setModalOpen(true)}>
          + Add API Key
        </Button>
      </div>

      {apiKeys.length === 0 ? (
        <div className="mt-8 flex flex-col items-center justify-center py-12 text-center">
          <Key className="mb-4 h-10 w-10 text-neutral-300" />
          <p className="text-sm text-neutral-500">No API keys configured</p>
        </div>
      ) : (
        <div className="mt-4 rounded-lg border border-neutral-200 px-4">
          {apiKeys.map((key) => (
            <ApiKeyRow key={key.id} apiKey={key} onRotate={actions.rotate} />
          ))}
        </div>
      )}

      <ApiKeyModal
        open={modalOpen}
        onSave={(service, key) => { actions.add(service, key); setModalOpen(false); }}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/api-keys-tab.test.tsx 2>&1 | tail -10`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/api-keys-tab.tsx frontend/src/components/settings/api-keys-tab.test.tsx
git commit -m "feat(dash-005): add ApiKeysTab with key list and add modal"
```

---

## Task 11: SeoDefaultsTab Component

**Files:**
- Create: `frontend/src/components/settings/seo-defaults-tab.tsx`
- Create: `frontend/src/components/settings/seo-defaults-tab.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/settings/seo-defaults-tab.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SeoDefaultsTab } from "./seo-defaults-tab";
import type { SeoDefaults } from "@/types/settings";

const mockDefaults: SeoDefaults = {
  autoMetaTags: true,
  keywordOptimization: true,
  autoCoverImages: false,
  includeCitations: true,
  humanReviewBeforePublish: true,
};

describe("SeoDefaultsTab", () => {
  it("renders all 5 toggle labels", () => {
    render(<SeoDefaultsTab defaults={mockDefaults} onToggle={vi.fn()} />);
    expect(screen.getByText("Auto-generate meta tags")).toBeInTheDocument();
    expect(screen.getByText("Keyword optimization")).toBeInTheDocument();
    expect(screen.getByText("Auto-generate cover images")).toBeInTheDocument();
    expect(screen.getByText("Include citations")).toBeInTheDocument();
    expect(screen.getByText("Human review before publish")).toBeInTheDocument();
  });

  it("renders description text", () => {
    render(<SeoDefaultsTab defaults={mockDefaults} onToggle={vi.fn()} />);
    expect(screen.getByText(/title and description meta tags/)).toBeInTheDocument();
  });

  it("renders correct toggle states", () => {
    render(<SeoDefaultsTab defaults={mockDefaults} onToggle={vi.fn()} />);
    const switches = screen.getAllByRole("switch");
    expect(switches[0]).toHaveAttribute("aria-checked", "true");
    expect(switches[2]).toHaveAttribute("aria-checked", "false");
  });

  it("calls onToggle when switch is clicked", () => {
    const handler = vi.fn();
    render(<SeoDefaultsTab defaults={mockDefaults} onToggle={handler} />);
    const switches = screen.getAllByRole("switch");
    fireEvent.click(switches[0]);
    expect(handler).toHaveBeenCalledWith("autoMetaTags");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/settings/seo-defaults-tab.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement SeoDefaultsTab**

Create `frontend/src/components/settings/seo-defaults-tab.tsx`:

```typescript
import { Switch } from "@/components/ui/switch";
import type { SeoDefaults } from "@/types/settings";

const SEO_OPTIONS: { key: keyof SeoDefaults; label: string; description: string }[] = [
  {
    key: "autoMetaTags",
    label: "Auto-generate meta tags",
    description: "Generate title and description meta tags automatically",
  },
  {
    key: "keywordOptimization",
    label: "Keyword optimization",
    description: "Optimize keyword density and placement in content",
  },
  {
    key: "autoCoverImages",
    label: "Auto-generate cover images",
    description: "Create AI-generated hero images for each article",
  },
  {
    key: "includeCitations",
    label: "Include citations",
    description: "Add inline citations and references section to articles",
  },
  {
    key: "humanReviewBeforePublish",
    label: "Human review before publish",
    description: "Require manual approval before publishing articles",
  },
];

interface SeoDefaultsTabProps {
  defaults: SeoDefaults;
  onToggle: (key: keyof SeoDefaults) => void;
}

export function SeoDefaultsTab({ defaults, onToggle }: SeoDefaultsTabProps) {
  return (
    <div>
      <h2 className="font-heading text-lg font-semibold text-neutral-900">SEO Defaults</h2>
      <div className="mt-4 rounded-lg border border-neutral-200">
        {SEO_OPTIONS.map(({ key, label, description }, i) => (
          <div
            key={key}
            className={`flex items-center justify-between px-4 py-3 ${
              i < SEO_OPTIONS.length - 1 ? "border-b border-neutral-100" : ""
            }`}
          >
            <div>
              <p className="text-sm font-semibold text-neutral-900">{label}</p>
              <p className="text-xs text-neutral-500">{description}</p>
            </div>
            <Switch
              checked={defaults[key]}
              onCheckedChange={() => onToggle(key)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/seo-defaults-tab.test.tsx 2>&1 | tail -10`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/seo-defaults-tab.tsx frontend/src/components/settings/seo-defaults-tab.test.tsx
git commit -m "feat(dash-005): add SeoDefaultsTab with toggle switches"
```

---

## Task 12: GeneralTab Component

**Files:**
- Create: `frontend/src/components/settings/general-tab.tsx`
- Create: `frontend/src/components/settings/general-tab.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/settings/general-tab.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GeneralTab } from "./general-tab";
import type { GeneralConfig } from "@/types/settings";

const mockConfig: GeneralConfig = {
  articleLengthTarget: "3000-5000",
  contentTone: "professional",
};

describe("GeneralTab", () => {
  it("renders both dropdowns", () => {
    render(<GeneralTab config={mockConfig} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText("Article Length Target")).toBeInTheDocument();
    expect(screen.getByLabelText("Content Tone")).toBeInTheDocument();
  });

  it("renders descriptions", () => {
    render(<GeneralTab config={mockConfig} onUpdate={vi.fn()} />);
    expect(screen.getByText(/Target word count/)).toBeInTheDocument();
    expect(screen.getByText(/Writing style/)).toBeInTheDocument();
  });

  it("calls onUpdate when article length changes", () => {
    const handler = vi.fn();
    render(<GeneralTab config={mockConfig} onUpdate={handler} />);
    fireEvent.change(screen.getByLabelText("Article Length Target"), {
      target: { value: "1000-2000" },
    });
    expect(handler).toHaveBeenCalledWith({ articleLengthTarget: "1000-2000" });
  });

  it("calls onUpdate when content tone changes", () => {
    const handler = vi.fn();
    render(<GeneralTab config={mockConfig} onUpdate={handler} />);
    fireEvent.change(screen.getByLabelText("Content Tone"), {
      target: { value: "casual" },
    });
    expect(handler).toHaveBeenCalledWith({ contentTone: "casual" });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/settings/general-tab.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement GeneralTab**

Create `frontend/src/components/settings/general-tab.tsx`:

```typescript
import type { GeneralConfig } from "@/types/settings";

interface GeneralTabProps {
  config: GeneralConfig;
  onUpdate: (updates: Partial<GeneralConfig>) => void;
}

const SELECT_CLASS =
  "mt-1 h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm";

export function GeneralTab({ config, onUpdate }: GeneralTabProps) {
  return (
    <div>
      <h2 className="font-heading text-lg font-semibold text-neutral-900">General</h2>
      <div className="mt-4 max-w-md space-y-6">
        <div>
          <label htmlFor="article-length" className="block text-sm font-medium text-neutral-700">
            Article Length Target
          </label>
          <select
            id="article-length"
            value={config.articleLengthTarget}
            onChange={(e) =>
              onUpdate({ articleLengthTarget: e.target.value as GeneralConfig["articleLengthTarget"] })
            }
            className={SELECT_CLASS}
          >
            <option value="1000-2000">1,000 – 2,000 words</option>
            <option value="3000-5000">3,000 – 5,000 words</option>
            <option value="5000-8000">5,000 – 8,000 words</option>
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Target word count range for generated articles
          </p>
        </div>

        <div>
          <label htmlFor="content-tone" className="block text-sm font-medium text-neutral-700">
            Content Tone
          </label>
          <select
            id="content-tone"
            value={config.contentTone}
            onChange={(e) =>
              onUpdate({ contentTone: e.target.value as GeneralConfig["contentTone"] })
            }
            className={SELECT_CLASS}
          >
            <option value="professional">Professional &amp; Analytical</option>
            <option value="casual">Casual &amp; Conversational</option>
            <option value="technical">Technical &amp; Detailed</option>
            <option value="educational">Educational &amp; Accessible</option>
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Writing style and tone for all generated content
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/settings/general-tab.test.tsx 2>&1 | tail -10`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/general-tab.tsx frontend/src/components/settings/general-tab.test.tsx
git commit -m "feat(dash-005): add GeneralTab with config dropdowns"
```

---

## Task 13: Settings Page Assembly

**Files:**
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx`

- [ ] **Step 1: Replace the placeholder page with the full settings page**

Overwrite `frontend/src/app/(dashboard)/settings/page.tsx`:

```typescript
"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { SettingsNav } from "@/components/settings/settings-nav";
import { DomainsTab } from "@/components/settings/domains-tab";
import { LlmConfigTab } from "@/components/settings/llm-config-tab";
import { ApiKeysTab } from "@/components/settings/api-keys-tab";
import { SeoDefaultsTab } from "@/components/settings/seo-defaults-tab";
import { GeneralTab } from "@/components/settings/general-tab";
import { useSettings } from "@/hooks/use-settings";
import type { SettingsTab } from "@/types/settings";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("domains");
  const [toast, setToast] = useState<string | null>(null);

  const settings = useSettings();

  function showToast(message: string) {
    setToast(message);
    setTimeout(() => setToast(null), 4000);
  }

  return (
    <div className="space-y-8">
      <Header
        title="Settings"
        subtitle="Configure domains, LLM models, API keys, and publishing defaults"
      />

      <div className="flex min-h-[480px] overflow-hidden rounded-lg border border-neutral-200">
        <SettingsNav activeTab={activeTab} onTabChange={setActiveTab} />

        <div className="flex-1 p-8">
          {activeTab === "domains" && (
            <DomainsTab
              domains={settings.domains}
              actions={{
                add: (data) => { settings.addDomain(data); showToast("Domain saved"); },
                update: (id, u) => { settings.updateDomain(id, u); showToast("Domain updated"); },
                delete: (id) => { settings.deleteDomain(id); showToast("Domain deleted"); },
              }}
            />
          )}

          {activeTab === "llm" && (
            <LlmConfigTab
              config={settings.llmConfig}
              onUpdate={(u) => { settings.updateLlmConfig(u); showToast("LLM config updated"); }}
            />
          )}

          {activeTab === "api-keys" && (
            <ApiKeysTab
              apiKeys={settings.apiKeys}
              actions={{
                add: (s, k) => { settings.addApiKey(s, k); showToast("API key added"); },
                rotate: (id, k) => { settings.rotateApiKey(id, k); showToast("API key rotated"); },
              }}
            />
          )}

          {activeTab === "seo" && (
            <SeoDefaultsTab
              defaults={settings.seoDefaults}
              onToggle={(key) => { settings.toggleSeoDefault(key); showToast("SEO setting updated"); }}
            />
          )}

          {activeTab === "general" && (
            <GeneralTab
              config={settings.generalConfig}
              onUpdate={(u) => { settings.updateGeneralConfig(u); showToast("Settings updated"); }}
            />
          )}
        </div>
      </div>

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-50 rounded-lg bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors.

- [ ] **Step 3: Run full test suite**

Run: `cd frontend && npx vitest run 2>&1 | tail -10`
Expected: All tests pass (91 existing + new settings tests).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\(dashboard\)/settings/page.tsx
git commit -m "feat(dash-005): assemble Settings page with all 5 tabs"
```

---

## Task 14: Final Verification and Cleanup

- [ ] **Step 1: Run full frontend test suite**

Run: `cd frontend && npx vitest run --reporter=verbose 2>&1 | tail -30`
Expected: All tests pass. Verify test count is 91 + (new tests from tasks 3-12).

- [ ] **Step 2: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit --pretty`
Expected: No errors.

- [ ] **Step 3: Run linter**

Run: `cd frontend && npx next lint 2>&1 | tail -10`
Expected: No warnings or errors.

- [ ] **Step 4: Verify dev server renders the page**

Run: `cd frontend && npx next build 2>&1 | tail -15`
Expected: Build succeeds. Settings page included in output.

- [ ] **Step 5: Final commit if any cleanup was needed**

Only if fixups were made in this task:
```bash
git add -A && git commit -m "fix(dash-005): address linting and build issues"
```
