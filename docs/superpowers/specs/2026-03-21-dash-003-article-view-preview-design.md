# DASH-003: Article View & Preview — Design Specification

> **Date**: 2026-03-21
> **Status**: Draft
> **Ticket**: DASH-003
> **Depends on**: DASH-001 (Dashboard Overview — Done), DESIGN-005 (Article View Design — Done)
> **Design reference**: `pencil_designs/cognify.pen` → "Article View — Redesign" frame

---

## 1. Overview

The Article View feature adds two pages: a card grid listing all generated articles (`/articles`) and a two-column detail page for previewing a single article with markdown rendering, agent workflow panel, citations, and a mock publish flow (`/articles/[id]`).

**Routes**:
- `/articles` — replaces current `PagePlaceholder`
- `/articles/[id]` — new dynamic route for article detail

---

## 2. Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| List vs detail | Two separate pages (`/articles` + `/articles/[id]`) | Standard navigation pattern, URL-addressable articles |
| List layout | 2-column card grid | Consistent with Topic Discovery (DASH-002) pattern |
| Detail layout | Two-column (content ~65% + sidebar ~35%) | Everything visible without tab-switching; matches settings pattern |
| Markdown rendering | `react-markdown` | React-native, composable, supports plugins for future syntax highlighting |
| Publish action | Mock modal with platform checkboxes | Exercises UI patterns needed for Epic 5; mock-first like Settings |
| Backend | Mock-first | API exists (`GET /api/v1/articles/{id}`) but we use mock data until integration ticket |
| Article status | `"draft" | "complete" | "published"` | Maps to pipeline states; "complete" = ready to publish |

---

## 3. Article List Page (`/articles`)

### 3.1 Layout

```
┌─────────────────────────────────────────────────────┐
│ Header: "Articles"                                   │
│ Subtitle: "Review and publish generated articles"    │
├─────────────────────────────────────────────────────┤
│ ┌──────────────────────┐ ┌──────────────────────┐   │
│ │  [Domain] [Status]   │ │  [Domain] [Status]   │   │
│ │  Article Title       │ │  Article Title       │   │
│ │  Summary excerpt...  │ │  Summary excerpt...  │   │
│ │  3,200 words · 2h    │ │  2,800 words · 5h    │   │
│ └──────────────────────┘ └──────────────────────┘   │
│ ┌──────────────────────┐ ┌──────────────────────┐   │
│ │  ...                 │ │  ...                 │   │
│ └──────────────────────┘ └──────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 3.2 Article Card

Each card displays:
- **Top row**: Domain badge (colored, from existing `DomainBadge`) + Status badge (Draft=yellow, Complete=green, Published=primary/red)
- **Title**: Bold, 1-2 lines, truncated with ellipsis if needed
- **Summary**: 2 lines from `CanonicalArticle.summary`, text-neutral-500
- **Footer**: Word count (computed from `body_markdown`) + relative time (`generated_at`) on left, "View →" link (text-primary) on right

Clicking the card or "View →" navigates to `/articles/[id]`.

### 3.3 Empty State

Same pattern as Topic Discovery:
- FileText icon (lucide-react), neutral-300
- "No articles generated yet"
- "Articles will appear here after content generation completes."

### 3.4 Mock Data

4 articles:
1. "AI-Powered Phishing Detection Trends" — cybersecurity, complete, 3200 words, 2h ago
2. "Zero Trust Architecture in 2026" — cybersecurity, complete, 2800 words, 5h ago
3. "Transformer Models: State of the Art" — ai-ml, draft, 4100 words, 1d ago
4. "Cloud Security Best Practices" — cybersecurity, published, 2500 words, 2d ago

---

## 4. Article Detail Page (`/articles/[id]`)

### 4.1 Layout

```
┌─────────────────────────────────────────────────────┐
│ ← Back to Articles                                   │
│ Header: "Article Title"                              │
│ Subtitle · AI Generated · content_type badge         │
├─────────────────────────────────────────────────────┤
│ ┌──────────────────────────┐ ┌──────────────────┐   │
│ │                          │ │ PUBLISH           │   │
│ │  Markdown body           │ │ [Publish Article] │   │
│ │  rendered via            │ ├──────────────────┤   │
│ │  react-markdown          │ │ METADATA          │   │
│ │                          │ │ Domain: Cyber     │   │
│ │  H2 headings             │ │ Type: Analysis    │   │
│ │  Paragraphs              │ │ Words: 3,200      │   │
│ │  Inline citations [1]    │ │ Generated: 2h ago │   │
│ │                          │ ├──────────────────┤   │
│ │                          │ │ AGENT WORKFLOW    │   │
│ │                          │ │ ✓ Research (45s)  │   │
│ │                          │ │ ✓ Outline (12s)   │   │
│ │                          │ │ ✓ Drafting (90s)  │   │
│ │                          │ │ ✓ Humanize (15s)  │   │
│ │                          │ │ ✓ SEO (8s)        │   │
│ │                          │ │ ✓ Finalized (3s)  │   │
│ │──────────────────────────│ ├──────────────────┤   │
│ │ SOURCES                  │ │ KEY CLAIMS        │   │
│ │ [1] Title — url          │ │ • Claim one       │   │
│ │ [2] Title — url          │ │ • Claim two       │   │
│ │ [3] Title — url          │ │ • Claim three     │   │
│ └──────────────────────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 4.2 Left Column — Article Content

**Back link**: `← Back to Articles` at the top, links to `/articles`.

**Article header** (inside the content area):
- Title rendered as `<h1>` via markdown or explicit element
- Subtitle below title if present (text-neutral-500)
- AI disclosure badge if `ai_generated` is true: small pill "AI Generated" (bg-amber-100 text-amber-700)
- Content type badge: "Analysis", "Article", etc. (bg-neutral-100 text-neutral-600)

**Markdown body**: `body_markdown` rendered via `react-markdown`. Apply Tailwind typography styles:
- `prose` class for consistent heading/paragraph/list spacing
- H2 sections with bottom border
- Inline citation markers `[1]` styled as superscript links (scroll to sources section)
- Code blocks with background shading if present

**Sources section** (below markdown, inside left column):
- Section header: "Sources" with count badge
- Numbered list matching citation indices
- Each entry: `[index] Title` as a link to `url`, authors and date below if available

### 4.3 Right Column — Sidebar

Four stacked cards, each with a section header (uppercase label, neutral-400):

**1. Publish Card** (top, highlighted border):
- "Publish Article" primary button, full width
- Clicking opens `PublishModal`

**2. Metadata Card**:
- Domain badge (reuse `DomainBadge`)
- Content type: "Analysis", "Article", etc.
- Word count (computed from body_markdown split by whitespace)
- Author(s)
- Generated: relative time from `generated_at`

**3. Agent Workflow Card**:
- List of pipeline steps, each with:
  - Green checkmark icon (Check from lucide-react)
  - Step name
  - Duration in parentheses
- Steps (mock data): Research, Outline, Drafting, Humanization, SEO, Finalized
- Each step has a mock duration (stored in mock data)

**4. Key Claims Card**:
- Bulleted list of `key_claims` from the article
- Each claim as a concise sentence

### 4.4 Not-Found State

If article ID doesn't match any mock article:
- FileText icon, neutral-300
- "Article not found"
- "← Back to Articles" link

---

## 5. Publish Modal

**Trigger**: "Publish Article" button in sidebar.

**Props**: `open: boolean`, `onClose: () => void`, `onPublish: (platforms: string[]) => void`

**Content**:
- Title: "Publish Article"
- Description: "Select platforms to publish this article to."
- 4 platform checkboxes: Ghost, WordPress, Medium, LinkedIn
- Each checkbox with platform icon/name
- Cancel + "Publish" buttons (Publish disabled if no platforms selected)

**Mock behavior**: `onPublish` receives selected platform names. Parent shows toast "Article scheduled for publishing to [platforms]". No real API call.

**Pattern**: Same overlay modal pattern as `GenerateArticleModal` and `DomainModal`.

---

## 6. Types

All article view types in `frontend/src/types/articles.ts`:

```typescript
// --- Article List ---

export type ArticleStatus = "draft" | "complete" | "published";

export interface ArticleListItem {
  id: string;
  title: string;
  summary: string;
  domain: string;
  status: ArticleStatus;
  wordCount: number;
  generatedAt: string; // ISO datetime
}

// --- Article Detail (mirrors CanonicalArticleResponse) ---

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

Note: `WorkflowStep` and `wordCount` are frontend-only fields not present in the backend response. `wordCount` is computed from `bodyMarkdown.split(/\s+/).length` in mock data; when the real API is integrated, it will be computed the same way on the frontend. `visuals` is included to mirror the backend contract but will be an empty array until VISUAL-001+.

---

## 7. Migration & Compatibility

### 7.1 StatusBadge Extension

The existing `StatusBadge` component (`components/common/status-badge.tsx`) supports `"live" | "draft" | "scheduled" | "failed"`. We need to add two new statuses:

- `"complete"` — green styling (bg-success-light text-success), label "Complete"
- `"published"` — maps to existing `"live"` styling (bg-success-light text-success), label "Published"

Extend `STATUS_STYLES` and `STATUS_LABELS` in the existing component. The `ArticleCard` will use `StatusBadge` with these new values.

### 7.2 Existing `Article` Type in `types/api.ts`

The existing `Article` interface (`types/api.ts:27-33`) is used by the dashboard's "Recent Articles" list (`DASH-001`). It has fields `{id, title, status, published_at, views}` with status `"live" | "draft" | "scheduled" | "failed"`.

**Strategy**: Keep the existing `Article` type untouched in `types/api.ts` — it serves the dashboard's needs. The new `ArticleListItem` and `ArticleDetail` types in `types/articles.ts` are separate types for the articles pages. The two coexist:
- Dashboard uses `Article` (from `api.ts`) via existing `useArticles` hook
- Articles pages use `ArticleListItem` / `ArticleDetail` (from `articles.ts`) via new hooks

### 7.3 Hook Separation

The existing `useArticles` hook (`hooks/use-articles.ts`) is used by the dashboard and returns `Article[]` via React Query. **Do not modify it.**

Instead, create new hooks:
- `useArticleList` — returns `ArticleListItem[]` from mock data (new hook for the articles list page)
- `useArticle` — returns `ArticleDetail | null` by ID from mock data

Both new hooks use `useState` with mock data (same pattern as `useSettings`), keeping the dashboard's React Query hook untouched.

---

## 8. Data Flow

### 8.1 Hooks

**`useArticleList`** — `frontend/src/hooks/use-article-list.ts` (~20 lines)

New hook returning article list from mock data. Does NOT touch the existing `useArticles` hook.

```typescript
interface UseArticleListReturn {
  articles: ArticleListItem[];
}
```

**`useArticle`** — `frontend/src/hooks/use-article.ts` (~20 lines)

New hook returning a single article by ID from mock data.

```typescript
interface UseArticleReturn {
  article: ArticleDetail | null;
}
```

### 8.2 Page Composition

**Articles List:**
```
ArticlesPage
  ├── useArticleList()
  ├── Header (title + subtitle)
  ├── articles.length === 0 → EmptyState
  └── 2-col grid of ArticleCard (article, each links to /articles/[id])
```

**Article Detail:**
```
ArticleDetailPage
  ├── useArticle(id)
  ├── article === null → NotFoundState
  ├── "← Back to Articles" link
  ├── Header (title + badges)
  └── 2-col flex container
       ├── ArticleContent (bodyMarkdown, citations)
       └── ArticleSidebar (article, onPublish)
            ├── PublishCard → opens PublishModal
            ├── MetadataCard
            ├── WorkflowSteps (workflow)
            └── KeyClaimsCard
```

---

## 9. Edge Cases

| Scenario | Behavior |
|----------|----------|
| Article not found | Show not-found state with back link |
| No subtitle | Skip subtitle rendering |
| Empty key_claims | Hide Key Claims card |
| Empty citations | Show "No sources" in sources section |
| Long title | Truncate with ellipsis on card, full display on detail |
| Publish with no platforms selected | Publish button disabled |
| body_markdown with code blocks | Render with background shading via react-markdown |

---

## 10. File Structure

### New Files

```
frontend/src/
  app/(dashboard)/articles/[id]/page.tsx              — Article detail page
  components/articles/
    article-card.tsx + test                            — Card for list grid
    article-content.tsx + test                         — Markdown rendering + citations
    article-sidebar.tsx + test                         — Metadata, workflow, key claims
    publish-modal.tsx + test                           — Platform selection modal
    workflow-steps.tsx + test                          — Agent pipeline steps display
  hooks/
    use-article-list.ts + test                        — Article list from mock data
    use-article.ts + test                             — Single article by ID
  types/
    articles.ts                                       — All article view types
```

### Modified Files

```
frontend/src/
  app/(dashboard)/articles/page.tsx                   — Replace placeholder with card grid
  components/common/status-badge.tsx                   — Add "complete" and "published" statuses
  lib/mock/articles.ts                                — Replace with full ArticleDetail mock data
```

### New Dependency

```
react-markdown                                        — Markdown to React component renderer
```

### Estimated Sizes

| File | Lines |
|------|-------|
| `articles/[id]/page.tsx` | ~55 |
| `article-card.tsx` | ~45 |
| `article-content.tsx` | ~65 |
| `article-sidebar.tsx` | ~70 |
| `publish-modal.tsx` | ~75 |
| `workflow-steps.tsx` | ~35 |
| `use-article.ts` | ~20 |
| `use-articles.ts` (updated) | ~20 |
| `types/articles.ts` | ~55 |
| `lib/mock/articles.ts` (updated) | ~180 |
| `articles/page.tsx` (updated) | ~55 |

All under 200-line limit.

---

## 11. Testing Strategy

### Unit Tests (Vitest + React Testing Library)

| Component | Key Tests |
|-----------|-----------|
| `ArticleCard` | Renders title, summary, domain badge, status badge, word count, time; click navigates |
| `ArticleContent` | Renders markdown headings and paragraphs; renders citations list with links |
| `ArticleSidebar` | Renders metadata (domain, type, word count, date); renders workflow steps; renders key claims; publish button opens modal |
| `PublishModal` | Renders platform checkboxes; publish button disabled when none selected; calls onPublish with selected platforms; cancel closes |
| `WorkflowSteps` | Renders all steps with checkmarks; shows durations |
| `useArticleList` | Returns mock article list with correct length |
| `useArticle` | Returns article by ID; returns null for unknown ID |
| `StatusBadge` | Renders "Complete" and "Published" statuses with correct styling |

### Coverage Targets

- Components: 80%+
- Hook logic: 90%+
- Pages: render without errors
