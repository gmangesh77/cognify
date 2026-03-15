# DASH-001: Dashboard Overview — Design Spec

## 1. Overview

**Ticket**: DASH-001 — Dashboard Overview
**Goal**: Build the first frontend screen for Cognify — a Next.js 15 dashboard overview page that displays key metrics, trending topics, and recent articles. Scaffold the full app shell (all routes, sidebar nav, auth) with placeholder pages for screens not yet implemented.

**Key decisions**:
- Full UI with mock data for sections without backend endpoints (articles, metrics)
- TanStack Query for API state management (no RSC)
- Tailwind CSS + shadcn/ui for styling and components
- All 7 routes scaffolded with placeholder pages
- Domain label added above topic titles (not in original Pencil design)
- Space Grotesk + Inter fonts, Lucide icons (matching Pencil designs)

## 2. Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | Next.js 15 (App Router) | SSR framework, routing |
| UI Library | React 19 + TypeScript | Component rendering |
| Styling | Tailwind CSS | Utility-first CSS |
| Components | shadcn/ui | Accessible pre-built components |
| API State | TanStack Query (React Query) | Caching, refetching, server state |
| HTTP Client | Axios | API calls with interceptors |
| Icons | Lucide React | Icon library |
| Fonts | Space Grotesk + Inter (next/font/google) | Typography |
| Testing | Vitest + React Testing Library + Playwright | Unit, integration, E2E |
| Mock API | MSW (Mock Service Worker) | Test API mocking |

## 3. Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout (fonts, providers)
│   │   ├── (auth)/
│   │   │   └── login/page.tsx      # Login page
│   │   └── (dashboard)/
│   │       ├── layout.tsx          # Dashboard layout (sidebar + main)
│   │       ├── page.tsx            # Dashboard overview (this ticket)
│   │       ├── topics/page.tsx     # Placeholder
│   │       ├── articles/page.tsx   # Placeholder
│   │       ├── research/page.tsx   # Placeholder
│   │       ├── publishing/page.tsx # Placeholder
│   │       └── settings/page.tsx   # Placeholder
│   ├── components/
│   │   ├── ui/                     # shadcn/ui components
│   │   ├── layout/
│   │   │   ├── sidebar.tsx         # Sidebar navigation
│   │   │   └── header.tsx          # Page header with actions
│   │   ├── dashboard/
│   │   │   ├── metric-card.tsx     # Metric display card
│   │   │   ├── trending-topics-list.tsx  # Trending topics card
│   │   │   ├── topic-row.tsx       # Individual topic row
│   │   │   ├── recent-articles-list.tsx  # Recent articles card
│   │   │   └── article-row.tsx     # Individual article row
│   │   └── common/
│   │       ├── domain-badge.tsx    # Colored domain label
│   │       ├── trend-badge.tsx     # Trending/New/Rising/Steady pill
│   │       ├── status-badge.tsx    # Live/Draft/Scheduled/Failed pill
│   │       └── page-placeholder.tsx # "Coming Soon" empty state
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts          # Axios instance with auth interceptors
│   │   │   ├── auth.ts            # Login, refresh, logout functions
│   │   │   ├── trends.ts          # Trend fetching + ranking API calls
│   │   │   └── endpoints.ts       # API endpoint constants
│   │   ├── mock/
│   │   │   ├── metrics.ts         # Mock dashboard metrics
│   │   │   └── articles.ts        # Mock recent articles
│   │   └── utils.ts               # cn() helper, date formatters
│   ├── hooks/
│   │   ├── use-topics.ts          # TanStack Query hook for trending topics
│   │   ├── use-metrics.ts         # TanStack Query hook for metrics (mock)
│   │   └── use-articles.ts        # TanStack Query hook for articles (mock)
│   └── types/
│       ├── api.ts                 # Types matching backend Pydantic schemas
│       └── domain.ts              # Frontend-specific domain types
├── tailwind.config.ts
├── next.config.ts
├── tsconfig.json
└── package.json
```

## 4. Layout & Navigation

### Root Layout (`app/layout.tsx`)
- Loads Space Grotesk (headings) + Inter (body) via `next/font/google`
- Wraps app in `QueryClientProvider` (TanStack Query)
- Global Tailwind styles

### Dashboard Layout (`app/(dashboard)/layout.tsx`)
- Fixed sidebar (240px width) on left
- Scrollable main content area (flex-1) on right
- Sidebar background: `#F8FAFC`, right border `#E2E8F0`

### Sidebar Component
Matches Pencil design (`Component/Sidebar`):
- Cognify logo at top (32px top padding)
- 6 navigation items with 4px vertical gap:
  - Dashboard (LayoutDashboard icon) — active on `/`
  - Topics (Compass icon) — active on `/topics`
  - Articles (FileText icon) — active on `/articles`
  - Research (Search icon) — active on `/research`
  - Publishing (Send icon) — active on `/publishing`
  - Settings (Settings icon) — active on `/settings`
- Active state: primary red text (`#DC2626`), light red background
- Default state: neutral-500 text, transparent background, hover state

### Auth Layout (`app/(auth)/`)
- No sidebar, centered content
- Login form with Cognify branding
- Redirects to dashboard on successful login

### Auth Flow
- Login → `POST /api/v1/auth/login` → receives access + refresh tokens
- Access token stored in memory (React state/context) — never persisted to storage
- Refresh token stored in an `httpOnly`, `Secure`, `SameSite=Strict` cookie (set by backend on login/refresh responses). This prevents XSS-based token theft. **Backend change required**: `/auth/login` and `/auth/refresh` must set the refresh token as an httpOnly cookie in addition to (or instead of) returning it in the JSON body.
- Axios interceptor: attaches `Authorization: Bearer <access_token>` header; cookies sent automatically via `withCredentials: true`
- On 401 response: attempts silent refresh via `/auth/refresh` (cookie sent automatically), retries original request
- On refresh failure: redirects to login, clears QueryClient cache
- Protected routes redirect to `/login` if no auth state

## 5. Dashboard Overview Page

### Header Row
- Left: "Dashboard" title (Space Grotesk, 36px, 600 weight) + subtitle "Monitor trends, track articles, and manage your content pipeline." (Inter, 14px, `#64748B`)
- Right: "Search" ghost button (lucide search icon) + "New Scan" primary button (red `#DC2626`, lucide zap icon)
- "New Scan" non-functional for now (no scan endpoint)

### Metrics Row — 4 Cards
Horizontal row with 24px gap, responsive (2x2 grid on smaller screens).

| Card | Label | Mock Value | Mock Trend | Direction |
|------|-------|-----------|------------|-----------|
| Topics Discovered | Total topics found | 147 | +12% | up (green) |
| Articles Generated | Total articles | 38 | +18% | up (green) |
| Avg Research Time | Average duration | 4.2m | -15% | down (green, lower is better) |
| Published | Published count | 24 | +8% | up (green) |

Card styling: white bg, 1px border `#E2E8F0`, 8px radius, subtle shadow (y:4, blur:6, `#00000012`), 24px padding.

### Content Row — 2 Columns
Equal-width columns with 24px gap.

#### Left: Trending Topics List
- Card with "Trending Topics" header + "View All" link (red, navigates to `/topics`)
- 5 topic rows, each showing:
  - **Domain label** (new): uppercase, colored text above title (e.g., "CYBERSECURITY" in indigo `#6366F1`, "AI / ML" in emerald `#059669`)
  - Topic title (Space Grotesk, 14px, 500 weight)
  - Trend badge (Trending=red, New=blue, Rising=orange, Steady=slate `#64748B` on `#F1F5F9`) + source labels (gray text)
  - Composite score on right (Space Grotesk, 16px, 600 weight)
- Rows separated by 1px border, 14px vertical / 20px horizontal padding
- **Data source**: Mock data for DASH-001. The `useTopics()` hook returns mock `RankedTopic[]` with a `domain` field. When a backend `GET /api/v1/dashboard/topics` endpoint is built (which orchestrates trend fetching + ranking server-side), the hook swaps to the real endpoint. This avoids the frontend calling 5+ trend source endpoints directly, keeping orchestration in the backend per the architecture principle of separation of concerns.
- Auto-refetches every 15 minutes via TanStack Query (aligned with the 30-minute trend scan interval to avoid unnecessary API traffic)
- **Error state**: On API failure, show a card with "Unable to load trending topics" message + "Retry" button
- **Empty state**: When no topics returned, show "No trending topics found. Try adjusting your domain keywords." with an illustration
- **Loading state**: Show 5 skeleton rows matching the TopicRow layout (skeleton text blocks for domain, title, badges, score)
- **Role handling**: Viewer-role users see mock/cached data; trend-fetching endpoints require editor/admin role. The hook gracefully degrades for viewers.

#### Right: Recent Articles List
- Card with "Recent Articles" header + "View All" link (red, navigates to `/articles`)
- 4 article rows showing:
  - Article title (Space Grotesk, 14px, 500 weight)
  - Status badge (Live=green) + date (Inter, 13px)
  - View count with eye icon on right (Inter, 13px, `#475569`)
- **Data source**: Mock data (no articles endpoint yet)
- **Error state**: On failure, show "Unable to load recent articles" + "Retry" button
- **Empty state**: "No articles yet. Generate your first article from a trending topic."
- **Loading state**: Show 4 skeleton rows matching the ArticleRow layout

## 6. Design Tokens (Tailwind Config)

### Colors
```
primary:        #DC2626    (buttons, CTAs, active nav, links)
primary-light:  #FEF2F2    (trending badge bg, hover states)
secondary:      #1E293B    (dark text)
neutral-50:     #F8FAFC    (sidebar bg, surfaces)
neutral-400:    #94A3B8    (muted text, source labels)
neutral-500:    #64748B    (body text, metric labels)
neutral-900:    #0F172A    (headings, metric values)
border:         #E2E8F0    (all borders and dividers)
success:        #16A34A    (positive trends, "Live" badge)
info:           #2563EB    ("New" badge text)
info-light:     #EFF6FF    ("New" badge bg)
accent:         #F97316    ("Rising" badge text)
accent-light:   #FFF7ED    ("Rising" badge bg)
```

### Domain Colors
```
cybersecurity:  #6366F1    (indigo)
ai-ml:          #059669    (emerald)
cloud:          #0EA5E9    (sky)
devops:         #D946EF    (fuchsia)
default:        #64748B    (slate fallback)
```

### Typography
- Heading font: Space Grotesk (600 weight for values/titles, 500 for subtitles)
- Body font: Inter (400 for body, 500 for labels, 600 for emphasis)

### Spacing
4px grid: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64

### Border Radius
sm: 4px, md: 8px, lg: 12px, pill: 9999px

### Shadows
sm: `0 1px 2px rgba(0,0,0,0.05)`
md: `0 4px 6px -1px rgba(0,0,0,0.07)`

## 7. API Layer

### Client (`lib/api/client.ts`)
- Axios instance, base URL: `http://localhost:8000/api/v1` (configurable via env)
- Request interceptor: attaches `Authorization: Bearer <token>` + generates `X-Request-ID`
- Response interceptor: on 401, attempts token refresh, retries original request; on refresh failure, redirects to login

### TanStack Query Hooks
- `useTopics()` — returns mock `RankedTopic[]` (with `domain` field) for DASH-001. Structured to swap to a real `GET /api/v1/dashboard/topics` endpoint when built. Refetches every 15 minutes.
- `useMetrics()` — returns mock `DashboardMetrics` object, structured for easy swap to real endpoint
- `useArticles()` — returns mock `Article[]`, structured for easy swap

All hooks follow the same pattern: a query function that currently returns mock data, but accepts the same return type as the future real API response. Swapping mock → real is a one-line change in the query function.

### Mock Data (`lib/mock/`)
- `metrics.ts`: static `{ topicsDiscovered: 147, articlesGenerated: 38, avgResearchTime: "4.2m", published: 24 }` with trend percentages
- `articles.ts`: 4 articles with titles, dates, view counts, "Live" status

Each mock exports the same TypeScript type as the real API response shape.

## 8. Component Specifications

### MetricCard
Props: `label: string, value: string, trend: number, trendDirection: "up" | "down", positiveDirection?: "up" | "down"`
- Displays label, large value, colored trend arrow + percentage
- Green if trend direction matches positive direction, red otherwise

### TrendingTopicsList
Props: `topics: RankedTopic[], isLoading: boolean`
- Card wrapper with header row
- Renders `TopicRow` for each topic
- Shows skeleton loading state via shadcn Skeleton

### TopicRow
Props: `topic: RankedTopic` (where `RankedTopic` includes a `domain: string` field — the frontend type extends the backend schema with this field, derived from the ranking context or mock data)
- Domain label (colored uppercase text above title)
- Title, trend badge, source tags, score

### RecentArticlesList
Props: `articles: Article[], isLoading: boolean`
- Card wrapper with header row
- Renders `ArticleRow` for each article

### ArticleRow
Props: `article: Article`
- Title, status badge, date, view count

### DomainBadge
Props: `domain: string`
- Maps domain name to color from domain color palette
- Renders uppercase text with domain-specific color

### TrendBadge
Props: `variant: "trending" | "new" | "rising" | "steady"`
- Pill badge with variant-specific bg/text color

### StatusBadge
Props: `status: "live" | "draft" | "scheduled" | "failed"`
- Pill badge with status-specific bg/text color

### PagePlaceholder
Props: `title: string, icon: LucideIcon`
- Centered "Coming Soon" message with page icon and title

## 9. shadcn/ui Components to Install

`button`, `card`, `badge`, `input`, `separator`, `tooltip`, `avatar`, `dropdown-menu`, `skeleton`

## 10. Placeholder Pages

All non-dashboard routes render `PagePlaceholder` with appropriate icon and title:
- `/topics` — Compass icon, "Topic Discovery"
- `/articles` — FileText icon, "Articles"
- `/research` — Search icon, "Research Sessions"
- `/publishing` — Send icon, "Publishing"
- `/settings` — Settings icon, "Settings"

## 11. Testing Strategy

### Unit Tests (Vitest + React Testing Library)
- MetricCard renders value, label, correct trend arrow/color
- TrendBadge renders correct variant styles
- DomainBadge maps domain names to correct colors
- StatusBadge renders correct variant styles
- TopicRow displays domain label, title, score, badges
- ArticleRow displays title, status, date, view count
- Sidebar highlights active nav item based on current route

### Integration Tests (Vitest + MSW)
- TanStack Query hooks return correct data shapes
- Auth interceptor attaches token to requests
- 401 response triggers token refresh flow
- Dashboard page renders metrics, topics, and articles sections

### E2E Tests (Playwright)
- Login flow: enter credentials → redirected to dashboard
- Dashboard loads: metric cards visible, trending topics list populated, recent articles visible
- Sidebar navigation: clicking each nav item navigates to correct route
- Placeholder pages: each route shows "Coming Soon" with correct title

### Coverage Target
75% for frontend components (per TEST_STRATEGY.md)

## 12. Design Change from Pencil

**Addition: Domain label on topic cards**
- Not in original Pencil design (DESIGN-003/DESIGN-004)
- Added per user feedback: topics should show which domain they belong to
- Implementation: uppercase colored text label above topic title
- Applied to: Dashboard trending topics list, Topic Discovery screen (DASH-002)
- Domain color mapping: Cybersecurity=indigo, AI/ML=emerald, Cloud=sky, DevOps=fuchsia, default=slate

## 13. Environment Configuration

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_NAME=Cognify
```

- `.env.local` (git-ignored): actual values for local development
- `.env.example` (committed): template with placeholder values for developer onboarding

## 14. Out of Scope

- Dark mode (design tokens support it, but not implemented in DASH-001)
- WebSocket real-time updates (planned for RESEARCH-005)
- Responsive mobile layout (desktop-first per acceptance criteria)
- "New Scan" button functionality (no scan endpoint yet)
- Search functionality (no search endpoint yet)
