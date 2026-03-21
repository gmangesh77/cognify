# DASH-003: Article View & Preview — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Articles page placeholder with a card grid list and a two-column article detail page with markdown rendering, agent workflow panel, citations, and mock publish flow.

**Architecture:** Two pages — `/articles` (card grid listing) and `/articles/[id]` (two-column detail with content left, sidebar right). New `useArticleList` and `useArticle` hooks with mock data. Existing `useArticles` hook (dashboard) stays untouched. `react-markdown` for rendering article body.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind v4, react-markdown, Vitest, React Testing Library

**Spec:** `docs/superpowers/specs/2026-03-21-dash-003-article-view-preview-design.md`

**Baseline:** 156 frontend tests passing across 33 test files.

**Worktree:** `D:/Workbench/github/cognify-dash-003` on branch `feature/DASH-003-article-view-preview`

---

## File Structure

### New Files

| File | Responsibility | ~Lines |
|------|---------------|--------|
| `frontend/src/types/articles.ts` | All article view type definitions | ~70 |
| `frontend/src/lib/mock/article-details.ts` | Full ArticleDetail mock data (4 articles) | ~180 |
| `frontend/src/hooks/use-article-list.ts` | Article list from mock data | ~20 |
| `frontend/src/hooks/use-article-list.test.ts` | Hook tests | ~20 |
| `frontend/src/hooks/use-article.ts` | Single article by ID from mock data | ~15 |
| `frontend/src/hooks/use-article.test.ts` | Hook tests | ~25 |
| `frontend/src/components/articles/article-card.tsx` | Card for list grid | ~45 |
| `frontend/src/components/articles/article-card.test.tsx` | Card tests | ~50 |
| `frontend/src/components/articles/workflow-steps.tsx` | Agent pipeline steps display | ~35 |
| `frontend/src/components/articles/workflow-steps.test.tsx` | Steps tests | ~30 |
| `frontend/src/components/articles/article-content.tsx` | Markdown rendering + citations | ~65 |
| `frontend/src/components/articles/article-content.test.tsx` | Content tests | ~45 |
| `frontend/src/components/articles/article-sidebar.tsx` | Metadata, workflow, key claims, publish button | ~75 |
| `frontend/src/components/articles/article-sidebar.test.tsx` | Sidebar tests | ~55 |
| `frontend/src/components/articles/publish-modal.tsx` | Platform selection modal | ~75 |
| `frontend/src/components/articles/publish-modal.test.tsx` | Modal tests | ~60 |
| `frontend/src/app/(dashboard)/articles/[id]/page.tsx` | Article detail page | ~55 |

### Modified Files

| File | Change |
|------|--------|
| `frontend/src/components/common/status-badge.tsx` | Add "complete" and "published" statuses |
| `frontend/src/app/(dashboard)/articles/page.tsx` | Replace placeholder with card grid (~55 lines) |

---

## Task 1: Install react-markdown and Types

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install react-markdown**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npm install react-markdown`

- [ ] **Step 2: Verify it installed**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && node -e "require('react-markdown'); console.log('OK')"`
Expected: "OK"

- [ ] **Step 3: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add frontend/package.json frontend/package-lock.json && git commit -m "chore(dash-003): add react-markdown dependency"
```

---

## Task 2: Article Types and Mock Data

**Files:**
- Create: `frontend/src/types/articles.ts`
- Create: `frontend/src/lib/mock/article-details.ts`

- [ ] **Step 1: Create article type definitions**

Create `frontend/src/types/articles.ts`:

```typescript
export type ArticleStatus = "draft" | "complete" | "published";

export interface ArticleListItem {
  id: string;
  title: string;
  summary: string;
  domain: string;
  status: ArticleStatus;
  wordCount: number;
  generatedAt: string;
}

export interface Citation {
  index: number;
  title: string;
  url: string;
  authors: string[];
  publishedAt: string | null;
}

export interface Provenance {
  researchSessionId: string;
  primaryModel: string;
  draftingModel: string;
  embeddingModel: string;
  embeddingVersion: string;
}

export interface StructuredDataLD {
  headline: string;
  description: string;
  keywords: string[];
  datePublished: string;
  dateModified: string;
}

export interface SEOMetadata {
  title: string;
  description: string;
  keywords: string[];
  canonicalUrl: string | null;
  structuredData: StructuredDataLD | null;
}

export interface ImageAsset {
  id: string;
  url: string;
  caption: string | null;
  altText: string | null;
}

export interface WorkflowStep {
  name: string;
  durationSeconds: number;
}

export interface ArticleDetail {
  id: string;
  title: string;
  subtitle: string | null;
  bodyMarkdown: string;
  summary: string;
  keyClaims: string[];
  contentType: string;
  seo: SEOMetadata;
  citations: Citation[];
  visuals: ImageAsset[];
  authors: string[];
  domain: string;
  generatedAt: string;
  provenance: Provenance;
  aiGenerated: boolean;
  status: ArticleStatus;
  wordCount: number;
  workflow: WorkflowStep[];
}
```

- [ ] **Step 2: Create mock data**

Create `frontend/src/lib/mock/article-details.ts` with 4 full `ArticleDetail` objects. Each article should have:
- Realistic markdown `bodyMarkdown` with 2-3 H2 sections, paragraphs, and inline `[1]` `[2]` citation markers
- 5-6 citations with URLs, titles, authors
- 3-5 key claims
- Provenance with model names
- Workflow steps (Research, Outline, Drafting, Humanization, SEO, Finalized) with realistic durations
- `wordCount` computed as `bodyMarkdown.split(/\s+/).length`

Articles:
1. `art-001`: "AI-Powered Phishing Detection Trends" — cybersecurity, complete, ~3200 words
2. `art-002`: "Zero Trust Architecture in 2026" — cybersecurity, complete, ~2800 words
3. `art-003`: "Transformer Models: State of the Art" — ai-ml, draft, ~4100 words
4. `art-004`: "Cloud Security Best Practices" — cybersecurity, published, ~2500 words

Also export a derived `articleListItems: ArticleListItem[]` computed from the details array (id, title, summary, domain, status, wordCount, generatedAt).

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add frontend/src/types/articles.ts frontend/src/lib/mock/article-details.ts && git commit -m "feat(dash-003): add article types and mock data"
```

---

## Task 3: Extend StatusBadge

**Files:**
- Modify: `frontend/src/components/common/status-badge.tsx`

- [ ] **Step 1: Add "complete" and "published" statuses**

In `frontend/src/components/common/status-badge.tsx`, add entries to both `STATUS_STYLES` and `STATUS_LABELS`:

```typescript
const STATUS_STYLES = {
  live: "bg-success-light text-success",
  draft: "bg-steady-light text-steady",
  scheduled: "bg-accent-light text-accent",
  failed: "bg-primary-light text-primary",
  complete: "bg-success-light text-success",
  published: "bg-success-light text-success",
} as const;

const STATUS_LABELS = {
  live: "Live",
  draft: "Draft",
  scheduled: "Scheduled",
  failed: "Failed",
  complete: "Complete",
  published: "Published",
} as const;
```

- [ ] **Step 2: Add tests for new statuses**

Add to the existing test file `frontend/src/components/common/status-badge.test.tsx`:

```typescript
it("renders complete status", () => {
  render(<StatusBadge status="complete" />);
  expect(screen.getByText("Complete")).toBeInTheDocument();
});

it("renders published status", () => {
  render(<StatusBadge status="published" />);
  expect(screen.getByText("Published")).toBeInTheDocument();
});
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/common/status-badge.test.tsx 2>&1 | tail -10`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add frontend/src/components/common/status-badge.tsx frontend/src/components/common/status-badge.test.tsx && git commit -m "feat(dash-003): extend StatusBadge with complete and published statuses"
```

---

## Task 4: useArticleList and useArticle Hooks

**Files:**
- Create: `frontend/src/hooks/use-article-list.ts`
- Create: `frontend/src/hooks/use-article-list.test.ts`
- Create: `frontend/src/hooks/use-article.ts`
- Create: `frontend/src/hooks/use-article.test.ts`

- [ ] **Step 1: Write failing tests for useArticleList**

Create `frontend/src/hooks/use-article-list.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useArticleList } from "./use-article-list";

describe("useArticleList", () => {
  it("returns mock articles", () => {
    const { result } = renderHook(() => useArticleList());
    expect(result.current.articles.length).toBeGreaterThan(0);
  });

  it("each article has required fields", () => {
    const { result } = renderHook(() => useArticleList());
    const article = result.current.articles[0];
    expect(article.id).toBeDefined();
    expect(article.title).toBeDefined();
    expect(article.summary).toBeDefined();
    expect(article.domain).toBeDefined();
    expect(article.status).toBeDefined();
    expect(article.wordCount).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Write failing tests for useArticle**

Create `frontend/src/hooks/use-article.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useArticle } from "./use-article";

describe("useArticle", () => {
  it("returns article by ID", () => {
    const { result } = renderHook(() => useArticle("art-001"));
    expect(result.current.article).not.toBeNull();
    expect(result.current.article?.title).toContain("Phishing");
  });

  it("returns null for unknown ID", () => {
    const { result } = renderHook(() => useArticle("nonexistent"));
    expect(result.current.article).toBeNull();
  });

  it("article has full detail fields", () => {
    const { result } = renderHook(() => useArticle("art-001"));
    const a = result.current.article!;
    expect(a.bodyMarkdown.length).toBeGreaterThan(0);
    expect(a.citations.length).toBeGreaterThanOrEqual(5);
    expect(a.keyClaims.length).toBeGreaterThanOrEqual(3);
    expect(a.workflow.length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/hooks/use-article-list.test.ts src/hooks/use-article.test.ts 2>&1 | tail -10`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement useArticleList**

Create `frontend/src/hooks/use-article-list.ts`:

```typescript
import { articleListItems } from "@/lib/mock/article-details";
import type { ArticleListItem } from "@/types/articles";

interface UseArticleListReturn {
  articles: ArticleListItem[];
}

export function useArticleList(): UseArticleListReturn {
  return { articles: articleListItems };
}
```

- [ ] **Step 5: Implement useArticle**

Create `frontend/src/hooks/use-article.ts`:

```typescript
import { mockArticleDetails } from "@/lib/mock/article-details";
import type { ArticleDetail } from "@/types/articles";

interface UseArticleReturn {
  article: ArticleDetail | null;
}

export function useArticle(id: string): UseArticleReturn {
  const article = mockArticleDetails.find((a) => a.id === id) ?? null;
  return { article };
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/hooks/use-article-list.test.ts src/hooks/use-article.test.ts 2>&1 | tail -10`
Expected: 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add frontend/src/hooks/use-article-list.ts frontend/src/hooks/use-article-list.test.ts frontend/src/hooks/use-article.ts frontend/src/hooks/use-article.test.ts && git commit -m "feat(dash-003): add useArticleList and useArticle hooks"
```

---

## Task 5: ArticleCard Component

**Files:**
- Create: `frontend/src/components/articles/article-card.tsx`
- Create: `frontend/src/components/articles/article-card.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/articles/article-card.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ArticleCard } from "./article-card";
import type { ArticleListItem } from "@/types/articles";

const mockArticle: ArticleListItem = {
  id: "art-001",
  title: "AI-Powered Phishing Detection Trends",
  summary: "New machine learning approaches to detecting sophisticated phishing attacks",
  domain: "cybersecurity",
  status: "complete",
  wordCount: 3200,
  generatedAt: new Date().toISOString(),
};

describe("ArticleCard", () => {
  it("renders title", () => {
    render(<ArticleCard article={mockArticle} />);
    expect(screen.getByText("AI-Powered Phishing Detection Trends")).toBeInTheDocument();
  });

  it("renders summary", () => {
    render(<ArticleCard article={mockArticle} />);
    expect(screen.getByText(/machine learning approaches/)).toBeInTheDocument();
  });

  it("renders domain badge", () => {
    render(<ArticleCard article={mockArticle} />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
  });

  it("renders status badge", () => {
    render(<ArticleCard article={mockArticle} />);
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("renders word count", () => {
    render(<ArticleCard article={mockArticle} />);
    expect(screen.getByText(/3,200 words/)).toBeInTheDocument();
  });

  it("has link to article detail", () => {
    render(<ArticleCard article={mockArticle} />);
    const link = screen.getByText("View →");
    expect(link.closest("a")).toHaveAttribute("href", "/articles/art-001");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/articles/article-card.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement ArticleCard**

Create `frontend/src/components/articles/article-card.tsx`:

```typescript
import Link from "next/link";
import { DomainBadge } from "@/components/common/domain-badge";
import { StatusBadge } from "@/components/common/status-badge";
import type { ArticleListItem } from "@/types/articles";

interface ArticleCardProps {
  article: ArticleListItem;
}

function formatTimeAgo(dateStr: string): string {
  const hours = Math.floor((Date.now() - new Date(dateStr).getTime()) / 3600000);
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function ArticleCard({ article }: ArticleCardProps) {
  return (
    <div className="flex flex-col justify-between rounded-lg border border-neutral-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div>
        <div className="flex items-center gap-2">
          <DomainBadge domain={article.domain} />
          <StatusBadge status={article.status} />
        </div>
        <h3 className="mt-3 font-heading text-base font-semibold text-neutral-900 line-clamp-2">
          {article.title}
        </h3>
        <p className="mt-1.5 line-clamp-2 text-sm text-neutral-500">{article.summary}</p>
      </div>
      <div className="mt-4 flex items-center justify-between text-xs text-neutral-400">
        <span>{article.wordCount.toLocaleString()} words &middot; {formatTimeAgo(article.generatedAt)}</span>
        <Link href={`/articles/${article.id}`} className="font-medium text-primary hover:underline">
          View &rarr;
        </Link>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/articles/article-card.test.tsx 2>&1 | tail -10`
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add frontend/src/components/articles/article-card.tsx frontend/src/components/articles/article-card.test.tsx && git commit -m "feat(dash-003): add ArticleCard component"
```

---

## Task 6: WorkflowSteps Component

**Files:**
- Create: `frontend/src/components/articles/workflow-steps.tsx`
- Create: `frontend/src/components/articles/workflow-steps.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/articles/workflow-steps.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WorkflowSteps } from "./workflow-steps";
import type { WorkflowStep } from "@/types/articles";

const mockSteps: WorkflowStep[] = [
  { name: "Research", durationSeconds: 45 },
  { name: "Outline", durationSeconds: 12 },
  { name: "Drafting", durationSeconds: 90 },
];

describe("WorkflowSteps", () => {
  it("renders all step names", () => {
    render(<WorkflowSteps steps={mockSteps} />);
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Outline")).toBeInTheDocument();
    expect(screen.getByText("Drafting")).toBeInTheDocument();
  });

  it("renders durations", () => {
    render(<WorkflowSteps steps={mockSteps} />);
    expect(screen.getByText("(45s)")).toBeInTheDocument();
    expect(screen.getByText("(12s)")).toBeInTheDocument();
    expect(screen.getByText("(90s)")).toBeInTheDocument();
  });

  it("renders checkmark icons", () => {
    const { container } = render(<WorkflowSteps steps={mockSteps} />);
    const checks = container.querySelectorAll("[data-testid='step-check']");
    expect(checks).toHaveLength(3);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/articles/workflow-steps.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement WorkflowSteps**

Create `frontend/src/components/articles/workflow-steps.tsx`:

```typescript
import { Check } from "lucide-react";
import type { WorkflowStep } from "@/types/articles";

interface WorkflowStepsProps {
  steps: WorkflowStep[];
}

export function WorkflowSteps({ steps }: WorkflowStepsProps) {
  return (
    <div className="space-y-2">
      {steps.map((step) => (
        <div key={step.name} className="flex items-center gap-2 text-sm">
          <Check data-testid="step-check" className="h-4 w-4 text-success" />
          <span className="text-neutral-700">{step.name}</span>
          <span className="text-neutral-400">({step.durationSeconds}s)</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/articles/workflow-steps.test.tsx 2>&1 | tail -10`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add frontend/src/components/articles/workflow-steps.tsx frontend/src/components/articles/workflow-steps.test.tsx && git commit -m "feat(dash-003): add WorkflowSteps component"
```

---

## Task 7: ArticleContent Component

**Files:**
- Create: `frontend/src/components/articles/article-content.tsx`
- Create: `frontend/src/components/articles/article-content.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/articles/article-content.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ArticleContent } from "./article-content";
import type { Citation } from "@/types/articles";

const mockMarkdown = "## Introduction\n\nThis is a test article about security [1].\n\n## Key Findings\n\nImportant findings here [2].";

const mockCitations: Citation[] = [
  { index: 1, title: "Security Report 2026", url: "https://example.com/report", authors: ["John Doe"], publishedAt: "2026-01-15T00:00:00Z" },
  { index: 2, title: "Threat Analysis", url: "https://example.com/threats", authors: ["Jane Smith"], publishedAt: null },
];

describe("ArticleContent", () => {
  it("renders markdown headings", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} />);
    expect(screen.getByText("Introduction")).toBeInTheDocument();
    expect(screen.getByText("Key Findings")).toBeInTheDocument();
  });

  it("renders markdown paragraphs", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} />);
    expect(screen.getByText(/test article about security/)).toBeInTheDocument();
  });

  it("renders sources section header", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} />);
    expect(screen.getByText("Sources")).toBeInTheDocument();
  });

  it("renders citation titles as links", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} />);
    const link = screen.getByText("Security Report 2026");
    expect(link.closest("a")).toHaveAttribute("href", "https://example.com/report");
  });

  it("renders citation authors", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={mockCitations} />);
    expect(screen.getByText(/John Doe/)).toBeInTheDocument();
  });

  it("shows no sources message when citations empty", () => {
    render(<ArticleContent bodyMarkdown={mockMarkdown} citations={[]} />);
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("No sources")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/articles/article-content.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement ArticleContent**

Create `frontend/src/components/articles/article-content.tsx`:

```typescript
import Markdown from "react-markdown";
import type { Citation } from "@/types/articles";

interface ArticleContentProps {
  bodyMarkdown: string;
  citations: Citation[];
}

export function ArticleContent({ bodyMarkdown, citations }: ArticleContentProps) {
  return (
    <div>
      <div className="prose prose-neutral max-w-none prose-headings:font-heading prose-h2:border-b prose-h2:border-neutral-200 prose-h2:pb-2">
        <Markdown>{bodyMarkdown}</Markdown>
      </div>

      <div className="mt-8 border-t border-neutral-200 pt-6">
        <h3 className="font-heading text-base font-semibold text-neutral-900">Sources</h3>
        {citations.length === 0 ? (
          <p className="mt-3 text-sm text-neutral-500">No sources</p>
        ) : (
          <ol className="mt-3 space-y-2">
            {citations.map((citation) => (
              <li key={citation.index} className="text-sm">
                <span className="font-medium text-neutral-400">[{citation.index}]</span>{" "}
                <a
                  href={citation.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-primary hover:underline"
                >
                  {citation.title}
                </a>
                {citation.authors.length > 0 && (
                  <span className="text-neutral-500"> — {citation.authors.join(", ")}</span>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/articles/article-content.test.tsx 2>&1 | tail -10`
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add frontend/src/components/articles/article-content.tsx frontend/src/components/articles/article-content.test.tsx && git commit -m "feat(dash-003): add ArticleContent with markdown rendering and citations"
```

---

## Task 8: PublishModal Component

**Files:**
- Create: `frontend/src/components/articles/publish-modal.tsx`
- Create: `frontend/src/components/articles/publish-modal.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/articles/publish-modal.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PublishModal } from "./publish-modal";

describe("PublishModal", () => {
  it("renders nothing when open is false", () => {
    const { container } = render(
      <PublishModal open={false} onClose={vi.fn()} onPublish={vi.fn()} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders modal title when open", () => {
    render(<PublishModal open={true} onClose={vi.fn()} onPublish={vi.fn()} />);
    expect(screen.getByText("Publish Article")).toBeInTheDocument();
  });

  it("renders all 4 platform checkboxes", () => {
    render(<PublishModal open={true} onClose={vi.fn()} onPublish={vi.fn()} />);
    expect(screen.getByLabelText("Ghost")).toBeInTheDocument();
    expect(screen.getByLabelText("WordPress")).toBeInTheDocument();
    expect(screen.getByLabelText("Medium")).toBeInTheDocument();
    expect(screen.getByLabelText("LinkedIn")).toBeInTheDocument();
  });

  it("publish button disabled when no platforms selected", () => {
    render(<PublishModal open={true} onClose={vi.fn()} onPublish={vi.fn()} />);
    expect(screen.getByText("Publish")).toBeDisabled();
  });

  it("publish button enabled after selecting a platform", () => {
    render(<PublishModal open={true} onClose={vi.fn()} onPublish={vi.fn()} />);
    fireEvent.click(screen.getByLabelText("Ghost"));
    expect(screen.getByText("Publish")).not.toBeDisabled();
  });

  it("calls onPublish with selected platforms", () => {
    const handler = vi.fn();
    render(<PublishModal open={true} onClose={vi.fn()} onPublish={handler} />);
    fireEvent.click(screen.getByLabelText("Ghost"));
    fireEvent.click(screen.getByLabelText("Medium"));
    fireEvent.click(screen.getByText("Publish"));
    expect(handler).toHaveBeenCalledWith(["ghost", "medium"]);
  });

  it("calls onClose when Cancel is clicked", () => {
    const handleClose = vi.fn();
    render(<PublishModal open={true} onClose={handleClose} onPublish={vi.fn()} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(handleClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/articles/publish-modal.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement PublishModal**

Create `frontend/src/components/articles/publish-modal.tsx`:

```typescript
import { useState } from "react";
import { Button } from "@/components/ui/button";

const PLATFORMS = [
  { value: "ghost", label: "Ghost" },
  { value: "wordpress", label: "WordPress" },
  { value: "medium", label: "Medium" },
  { value: "linkedin", label: "LinkedIn" },
];

interface PublishModalProps {
  open: boolean;
  onClose: () => void;
  onPublish: (platforms: string[]) => void;
}

export function PublishModal({ open, onClose, onPublish }: PublishModalProps) {
  const [selected, setSelected] = useState<string[]>([]);

  if (!open) return null;

  function toggle(platform: string) {
    setSelected((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform],
    );
  }

  function handlePublish() {
    onPublish(selected);
    setSelected([]);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div role="dialog" className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <h2 className="font-heading text-lg font-semibold text-neutral-900">Publish Article</h2>
        <p className="mt-1 text-sm text-neutral-500">Select platforms to publish this article to.</p>

        <div className="mt-4 space-y-3">
          {PLATFORMS.map(({ value, label }) => (
            <label key={value} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selected.includes(value)}
                onChange={() => toggle(value)}
                className="rounded"
                aria-label={label}
              />
              {label}
            </label>
          ))}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={selected.length === 0} onClick={handlePublish}>Publish</Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/articles/publish-modal.test.tsx 2>&1 | tail -10`
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add frontend/src/components/articles/publish-modal.tsx frontend/src/components/articles/publish-modal.test.tsx && git commit -m "feat(dash-003): add PublishModal with platform selection"
```

---

## Task 9: ArticleSidebar Component

**Files:**
- Create: `frontend/src/components/articles/article-sidebar.tsx`
- Create: `frontend/src/components/articles/article-sidebar.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/articles/article-sidebar.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ArticleSidebar } from "./article-sidebar";
import type { ArticleDetail } from "@/types/articles";

const mockArticle: Partial<ArticleDetail> = {
  domain: "cybersecurity",
  contentType: "analysis",
  wordCount: 3200,
  authors: ["Cognify"],
  generatedAt: new Date().toISOString(),
  keyClaims: ["AI detection improved by 40%", "Phishing attacks rose 25% in 2026"],
  workflow: [
    { name: "Research", durationSeconds: 45 },
    { name: "Outline", durationSeconds: 12 },
    { name: "Drafting", durationSeconds: 90 },
  ],
};

describe("ArticleSidebar", () => {
  it("renders publish button", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText("Publish Article")).toBeInTheDocument();
  });

  it("renders domain", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
  });

  it("renders word count", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText(/3,200/)).toBeInTheDocument();
  });

  it("renders workflow steps", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Drafting")).toBeInTheDocument();
  });

  it("renders key claims", () => {
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={vi.fn()} />);
    expect(screen.getByText(/AI detection improved/)).toBeInTheDocument();
    expect(screen.getByText(/Phishing attacks rose/)).toBeInTheDocument();
  });

  it("calls onPublish when publish button clicked", () => {
    const handler = vi.fn();
    render(<ArticleSidebar article={mockArticle as ArticleDetail} onPublish={handler} />);
    fireEvent.click(screen.getByText("Publish Article"));
    expect(handler).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/articles/article-sidebar.test.tsx 2>&1 | tail -10`
Expected: FAIL.

- [ ] **Step 3: Implement ArticleSidebar**

Create `frontend/src/components/articles/article-sidebar.tsx`:

```typescript
import { Button } from "@/components/ui/button";
import { DomainBadge } from "@/components/common/domain-badge";
import { WorkflowSteps } from "./workflow-steps";
import type { ArticleDetail } from "@/types/articles";

interface ArticleSidebarProps {
  article: ArticleDetail;
  onPublish: () => void;
}

function formatTimeAgo(dateStr: string): string {
  const hours = Math.floor((Date.now() - new Date(dateStr).getTime()) / 3600000);
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function ArticleSidebar({ article, onPublish }: ArticleSidebarProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
        <Button className="w-full" onClick={onPublish}>Publish Article</Button>
      </div>

      <div className="rounded-lg border border-neutral-200 p-4">
        <h4 className="text-xs font-medium uppercase text-neutral-400">Metadata</h4>
        <div className="mt-2 space-y-1.5 text-sm text-neutral-700">
          <div className="flex items-center gap-2">
            <span className="text-neutral-500">Domain:</span>
            <DomainBadge domain={article.domain} />
          </div>
          <div><span className="text-neutral-500">Type:</span> {article.contentType}</div>
          <div><span className="text-neutral-500">Words:</span> {article.wordCount.toLocaleString()}</div>
          <div><span className="text-neutral-500">Author:</span> {article.authors.join(", ")}</div>
          <div><span className="text-neutral-500">Generated:</span> {formatTimeAgo(article.generatedAt)}</div>
        </div>
      </div>

      <div className="rounded-lg border border-neutral-200 p-4">
        <h4 className="text-xs font-medium uppercase text-neutral-400">Agent Workflow</h4>
        <div className="mt-2">
          <WorkflowSteps steps={article.workflow} />
        </div>
      </div>

      {article.keyClaims.length > 0 && (
        <div className="rounded-lg border border-neutral-200 p-4">
          <h4 className="text-xs font-medium uppercase text-neutral-400">Key Claims</h4>
          <ul className="mt-2 space-y-1">
            {article.keyClaims.map((claim, i) => (
              <li key={i} className="text-sm text-neutral-700">
                <span className="text-neutral-400">&bull;</span> {claim}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run src/components/articles/article-sidebar.test.tsx 2>&1 | tail -10`
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add frontend/src/components/articles/article-sidebar.tsx frontend/src/components/articles/article-sidebar.test.tsx && git commit -m "feat(dash-003): add ArticleSidebar with metadata, workflow, and claims"
```

---

## Task 10: Articles List Page

**Files:**
- Modify: `frontend/src/app/(dashboard)/articles/page.tsx`

- [ ] **Step 1: Replace the placeholder with the article list page**

Overwrite `frontend/src/app/(dashboard)/articles/page.tsx`:

```typescript
"use client";

import { FileText } from "lucide-react";
import { Header } from "@/components/layout/header";
import { ArticleCard } from "@/components/articles/article-card";
import { useArticleList } from "@/hooks/use-article-list";

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <FileText className="mb-4 h-12 w-12 text-neutral-300" />
      <h3 className="font-heading text-lg font-semibold text-neutral-700">
        No articles generated yet
      </h3>
      <p className="mt-2 max-w-sm text-sm text-neutral-500">
        Articles will appear here after content generation completes.
      </p>
    </div>
  );
}

export default function ArticlesPage() {
  const { articles } = useArticleList();

  return (
    <div className="space-y-8">
      <Header
        title="Articles"
        subtitle="Review and publish generated articles"
      />

      {articles.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-2 gap-6">
          {articles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add "frontend/src/app/(dashboard)/articles/page.tsx" && git commit -m "feat(dash-003): replace articles placeholder with card grid list"
```

---

## Task 11: Article Detail Page

**Files:**
- Create: `frontend/src/app/(dashboard)/articles/[id]/page.tsx`

- [ ] **Step 1: Create the article detail page**

Create `frontend/src/app/(dashboard)/articles/[id]/page.tsx`:

```typescript
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, FileText } from "lucide-react";
import { Header } from "@/components/layout/header";
import { ArticleContent } from "@/components/articles/article-content";
import { ArticleSidebar } from "@/components/articles/article-sidebar";
import { PublishModal } from "@/components/articles/publish-modal";
import { useArticle } from "@/hooks/use-article";

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <FileText className="mb-4 h-12 w-12 text-neutral-300" />
      <h3 className="font-heading text-lg font-semibold text-neutral-700">Article not found</h3>
      <Link href="/articles" className="mt-4 text-sm font-medium text-primary hover:underline">
        &larr; Back to Articles
      </Link>
    </div>
  );
}

export default function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { article } = useArticle(id);
  const [publishOpen, setPublishOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  if (!article) return <NotFound />;

  function handlePublish(platforms: string[]) {
    setPublishOpen(false);
    setToast(`Article scheduled for publishing to ${platforms.join(", ")}`);
    setTimeout(() => setToast(null), 4000);
  }

  return (
    <div className="space-y-6">
      <Link href="/articles" className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-700">
        <ArrowLeft className="h-4 w-4" /> Back to Articles
      </Link>

      <Header title={article.title} subtitle={article.subtitle ?? ""}>
        <div className="flex items-center gap-2">
          {article.aiGenerated && (
            <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
              AI Generated
            </span>
          )}
          <span className="rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs font-medium text-neutral-600">
            {article.contentType}
          </span>
        </div>
      </Header>

      <div className="flex gap-8">
        <div className="min-w-0 flex-[2]">
          <ArticleContent bodyMarkdown={article.bodyMarkdown} citations={article.citations} />
        </div>
        <div className="w-80 shrink-0">
          <ArticleSidebar article={article} onPublish={() => setPublishOpen(true)} />
        </div>
      </div>

      <PublishModal open={publishOpen} onClose={() => setPublishOpen(false)} onPublish={handlePublish} />

      {toast && (
        <div role="status" className="fixed bottom-6 right-6 z-50 rounded-lg bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd D:/Workbench/github/cognify-dash-003 && git add "frontend/src/app/(dashboard)/articles/[id]/page.tsx" && git commit -m "feat(dash-003): add article detail page with two-column layout"
```

---

## Task 12: Final Verification

- [ ] **Step 1: Run full frontend test suite**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx vitest run --reporter=verbose 2>&1 | tail -30`
Expected: All tests pass. Verify test count is 156 + new tests.

- [ ] **Step 2: Run TypeScript check**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx tsc --noEmit --pretty`
Expected: No errors.

- [ ] **Step 3: Run linter**

Run: `cd D:/Workbench/github/cognify-dash-003/frontend && npx eslint src/ 2>&1 | tail -10`
Expected: No new errors from our files (pre-existing errors in use-topic-filters.ts and use-topic-pagination.ts are OK).

- [ ] **Step 4: Final commit if any cleanup was needed**

Only if fixups were made:
```bash
cd D:/Workbench/github/cognify-dash-003 && git add -A && git commit -m "fix(dash-003): address linting and build issues"
```
