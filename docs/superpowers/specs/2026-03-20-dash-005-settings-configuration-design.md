# DASH-005: Settings & Configuration Screen — Design Specification

> **Date**: 2026-03-20
> **Status**: Approved
> **Ticket**: DASH-005
> **Depends on**: DASH-001 (Dashboard Overview — Done), DESIGN-008 (Settings Design — Done)
> **Design reference**: `pencil_designs/cognify.pen` → "Settings — Redesign" frame

---

## 1. Overview

The Settings screen provides a tabbed interface for managing domain configurations, LLM models, API keys, SEO defaults, and general preferences. It follows the redesigned Pencil design with a left sub-navigation and right content area.

**Route**: `/settings` (replaces current `PagePlaceholder`)

---

## 2. Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope | All 5 tabs in one ticket | Tabs share layout; non-Domains tabs are simple forms |
| Domain management | Multi-domain with add/edit/delete | Follows redesigned Pencil design |
| Add/Edit domain UX | Modal dialog | Consistent with GenerateArticleModal pattern from DASH-002 |
| API key add | Predefined service dropdown + key field | Keeps it simple, avoids free-text service names |
| API key rotate | Confirmation dialog before rotate | Prevents accidental key invalidation |
| Save behavior | Hybrid: auto-save for toggles, explicit save for modals | Toggles feel instant; forms need explicit confirm |
| Tab navigation | Client-side state (single `/settings` page) | Simpler, fewer files, no deep linking needed |
| Backend | Mock-first | No settings API exists yet |

---

## 3. Page Layout

```
┌─────────────────────────────────────────────────────┐
│ Header: "Settings"                                   │
│ Subtitle: "Configure domains, LLM models, API keys, │
│            and publishing defaults"                  │
├─────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌────────────────────────────────────┐ │
│ │ Domains  │ │                                    │ │
│ │ LLM Conf │ │  (Active tab content area)         │ │
│ │ API Keys │ │                                    │ │
│ │ SEO Defs │ │                                    │ │
│ │ General  │ │                                    │ │
│ └──────────┘ └────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

Left sub-nav (200px, `#FAFAFA` background, right border) + right content area (flex-1, padding 32px). Active tab: red text on light red background (`$primary` on `$primary-light`, `border-radius: 8px`). Matches the Pencil "Settings — Redesign" frame.

---

## 4. Tab Contents

### 4.1 Domains Tab

Section header: "Domains" title + "+ Add Domain" secondary button (top-right).

**Domain card:**
- Active domain: `border: 2px solid $primary`, shadow
- Inactive domain: `border: 1px solid $border`, shadow
- Content: name (bold), status badge (Active green / Inactive gray), Edit link
- Details row: Trend Sources, Keywords, Articles (3-column with uppercase labels)

**Domain modal (Add/Edit):**
- Props: `domain: DomainConfig | null` (null = add mode), `onSave`, `onClose`, `onDelete`
- Fields: Domain Name (text input), Trend Sources (checkboxes for 5 sources), Keywords (comma-separated text input), Status (Active/Inactive dropdown)
- Delete button: only in edit mode, bottom-left, with confirmation ("Are you sure? This cannot be undone.")
- Cancel + Save Domain buttons bottom-right

**Mock data:** Cybersecurity (active, Google Trends/Reddit/HN, security/threats/CVE, 24 articles), AI & Machine Learning (inactive, arXiv/HN/Reddit, LLM/Transformers/GPT, 7 articles).

### 4.2 LLM Configuration Tab

Section header: "LLM Configuration" title.

Three dropdowns in a single-column form (max-width 400px):
- **Primary Model**: Claude Opus 4 (default), Claude Sonnet 4, GPT-4o. Description: "Used for final article synthesis and quality pass"
- **Drafting Model**: Claude Sonnet 4 (default), Claude Opus 4, GPT-4o mini. Description: "Used for section drafting and outline generation"
- **Image Generation**: Stable Diffusion XL (default), DALL-E 3, Midjourney. Description: "Used for article hero images and illustrations"

Each dropdown has a helper text below it. Changes auto-save with toast notification.

### 4.3 API Keys Tab

Section header: "API Keys" title + "+ Add API Key" secondary button (top-right).

**Key list** in a bordered container with divider rows:
- Each row: service name (bold), masked key (monospace, gray background), Active/Inactive badge, Rotate button (red outline)
- Rotate flow: confirmation dialog → clear old key → show input for new key → save

**Add API Key modal:**
- Props: `onSave`, `onClose`
- Fields: Service (dropdown: Anthropic, SerpAPI, Ghost Admin, NewsAPI, arXiv), API Key (text input, type=password with show/hide toggle)
- Save + Cancel buttons

**Mock data:** 4 keys (Anthropic, SerpAPI, Ghost Admin, NewsAPI) all active with masked values.

### 4.4 SEO Defaults Tab

Section header: "SEO Defaults" title.

5 toggle rows in a bordered container:
- **Auto-generate meta tags** — "Generate title and description meta tags automatically"
- **Keyword optimization** — "Optimize keyword density and placement in content"
- **Auto-generate cover images** — "Create AI-generated hero images for each article"
- **Include citations** — "Add inline citations and references section to articles"
- **Human review before publish** — "Require manual approval before publishing articles"

Each row: title (14px, bold) + description (12px, gray) on left, toggle switch on right. All default to ON. Toggles auto-save with toast.

### 4.5 General Tab

Section header: "General" title.

Two dropdowns in a single-column form (max-width 400px):
- **Article Length Target**: 1,000-2,000 words / 3,000-5,000 words (default) / 5,000-8,000 words. Description: "Target word count range for generated articles"
- **Content Tone**: Professional & Analytical (default) / Casual & Conversational / Technical & Detailed / Educational & Accessible. Description: "Writing style and tone for all generated content"

Changes auto-save with toast notification.

---

## 5. Types

```typescript
type SettingsTab = "domains" | "llm" | "api-keys" | "seo" | "general";

interface DomainConfig {
  id: string;
  name: string;
  status: "active" | "inactive";
  trendSources: string[];
  keywords: string[];
  articleCount: number;
}

interface ApiKeyConfig {
  id: string;
  service: string;
  maskedKey: string;
  status: "active" | "inactive";
}

interface LlmConfig {
  primaryModel: string;
  draftingModel: string;
  imageGeneration: string;
}

interface SeoDefaults {
  autoMetaTags: boolean;
  keywordOptimization: boolean;
  autoCoverImages: boolean;
  includeCitations: boolean;
  humanReviewBeforePublish: boolean;
}

interface GeneralConfig {
  articleLengthTarget: string;
  contentTone: string;
}
```

---

## 6. Data Flow

### 6.1 Hook: `useSettings`

**File**: `frontend/src/hooks/use-settings.ts` (~80 lines)

Single hook managing all settings state via `useState` with mock initial data. No TanStack Query since there's no real API yet.

```typescript
interface UseSettingsReturn {
  // Data
  domains: DomainConfig[];
  llmConfig: LlmConfig;
  apiKeys: ApiKeyConfig[];
  seoDefaults: SeoDefaults;
  generalConfig: GeneralConfig;

  // Domain actions
  addDomain: (domain: Omit<DomainConfig, "id" | "articleCount">) => void;
  updateDomain: (id: string, updates: Partial<DomainConfig>) => void;
  deleteDomain: (id: string) => void;

  // Config actions
  updateLlmConfig: (updates: Partial<LlmConfig>) => void;
  addApiKey: (service: string, key: string) => void;
  rotateApiKey: (id: string, newKey: string) => void;
  toggleSeoDefault: (key: keyof SeoDefaults) => void;
  updateGeneralConfig: (updates: Partial<GeneralConfig>) => void;
}
```

### 6.2 Page Composition

```
SettingsPage
  ├── useState<SettingsTab>("domains")
  ├── useSettings()
  ├── Header (title + subtitle)
  ├── SettingsNav (activeTab, onTabChange)
  └── Conditional render by activeTab:
       ├── "domains" → DomainsTab (domains, addDomain, updateDomain, deleteDomain)
       ├── "llm" → LlmConfigTab (llmConfig, updateLlmConfig)
       ├── "api-keys" → ApiKeysTab (apiKeys, addApiKey, rotateApiKey)
       ├── "seo" → SeoDefaultsTab (seoDefaults, toggleSeoDefault)
       └── "general" → GeneralTab (generalConfig, updateGeneralConfig)
```

### 6.3 Toast Notifications

Same pattern as DASH-002: inline `useState<string | null>` with `setTimeout` to clear after 4s. Toasts shown for:
- Domain saved/deleted
- LLM config updated
- API key added/rotated
- SEO toggle changed
- General config updated

---

## 7. Edge Cases

| Scenario | Behavior |
|----------|----------|
| Delete last domain | Allowed — empty domain list with guidance text |
| Add duplicate domain name | Allowed (no uniqueness constraint in mock) |
| Rotate key — cancel | Key unchanged, modal closes |
| Rotate key — confirm then enter new key | Old key replaced, masked value updates |
| Add API key for already-configured service | Allowed (replaces existing — mock behavior) |
| Empty keywords field in domain | Allowed — saves with empty array |
| Tab switch with unsaved modal | Modal stays open (overlay blocks tab nav) |

---

## 8. File Structure

### New Files

```
frontend/src/
  app/(dashboard)/settings/page.tsx                  — Settings page (replace placeholder)
  components/settings/
    settings-nav.tsx + test                           — Left sub-navigation
    domain-card.tsx + test                            — Single domain display card
    domain-modal.tsx + test                           — Add/Edit domain form modal
    domains-tab.tsx + test                            — Domain list + add button
    llm-config-tab.tsx + test                         — 3 model dropdowns
    api-key-row.tsx + test                            — Single API key row
    api-keys-tab.tsx + test                           — Key list + add modal
    seo-defaults-tab.tsx + test                       — 5 toggle switches
    general-tab.tsx + test                            — 2 config dropdowns
  components/ui/
    switch.tsx                                        — Toggle switch (new UI component)
  hooks/
    use-settings.ts + test                            — All settings state + CRUD
  lib/mock/
    settings.ts                                       — Mock settings data
```

### Modified Files

```
frontend/src/types/api.ts                            — Add settings types
```

### Estimated Sizes

| File | Lines |
|------|-------|
| `settings/page.tsx` | ~60 |
| `settings-nav.tsx` | ~35 |
| `domain-card.tsx` | ~50 |
| `domain-modal.tsx` | ~90 |
| `domains-tab.tsx` | ~50 |
| `llm-config-tab.tsx` | ~50 |
| `api-key-row.tsx` | ~50 |
| `api-keys-tab.tsx` | ~70 |
| `seo-defaults-tab.tsx` | ~60 |
| `general-tab.tsx` | ~45 |
| `switch.tsx` | ~25 |
| `use-settings.ts` | ~80 |
| `mock/settings.ts` | ~60 |

All under 200-line limit.

---

## 9. Testing Strategy

### Unit Tests (Vitest + React Testing Library)

| Component | Key Tests |
|-----------|-----------|
| `SettingsNav` | Renders 5 items; active state styling; calls onTabChange on click |
| `DomainCard` | Renders name, status badge, sources, keywords, articles; calls onEdit |
| `DomainModal` | Add mode (empty form); Edit mode (pre-filled); save calls onSave; delete with confirmation |
| `DomainsTab` | Renders domain cards; opens modal on Add/Edit |
| `LlmConfigTab` | Renders 3 dropdowns with values; calls onChange on select |
| `ApiKeyRow` | Renders masked key, status, rotate button; rotate shows confirmation |
| `ApiKeysTab` | Renders key rows; add button opens modal |
| `SeoDefaultsTab` | Renders 5 toggles with labels; toggle calls onChange |
| `GeneralTab` | Renders 2 dropdowns; calls onChange on select |
| `useSettings` | Add/edit/delete domain; update LLM config; add/rotate API key; toggle SEO default |

### Coverage Targets

- Components: 80%+
- Hook logic: 90%+
- Page: renders without errors, default tab is Domains

---

## 10. API Key Service List

Predefined services for the "Add API Key" dropdown:

| Service | Display Name |
|---------|-------------|
| `anthropic` | Anthropic API |
| `serpapi` | SerpAPI |
| `ghost` | Ghost Admin |
| `newsapi` | NewsAPI |
| `arxiv` | arXiv |

Defined as a constant `API_KEY_SERVICES` in `lib/mock/settings.ts`.
