# DASH-001: Dashboard Overview — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Cognify dashboard frontend — a Next.js 15 app with sidebar navigation, login page, dashboard overview (metrics, trending topics, recent articles), and placeholder pages for future screens.

**Architecture:** Next.js 15 App Router with TanStack Query for API state, Tailwind CSS + shadcn/ui for styling. All data comes from mock data for now except auth (which hits the real FastAPI backend). The app shell scaffolds all routes upfront with placeholder pages.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Axios, Lucide React, Space Grotesk + Inter fonts, Vitest + React Testing Library, Playwright

**Spec:** [`docs/superpowers/specs/2026-03-15-dash-001-dashboard-overview-design.md`](../specs/2026-03-15-dash-001-dashboard-overview-design.md)

---

## Chunk 1: Project Scaffolding & Configuration

### Task 1: Initialize Next.js Project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/.env.example`
- Create: `frontend/.env.local`
- Create: `frontend/.gitignore`

- [ ] **Step 1: Scaffold Next.js 15 app**

```bash
cd D:/Workbench/github/cognify
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --no-import-alias --use-npm
```

When prompted:
- TypeScript: Yes
- ESLint: Yes
- Tailwind CSS: Yes
- `src/` directory: Yes
- App Router: Yes
- Turbopack: Yes
- Import alias: No (use default `@/`)

- [ ] **Step 2: Verify the app runs**

```bash
cd frontend && npm run dev
```

Expected: Next.js dev server starts on http://localhost:3000 with default page.

- [ ] **Step 3: Create environment files**

Create `frontend/.env.example`:
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_NAME=Cognify
```

Create `frontend/.env.local`:
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_NAME=Cognify
```

- [ ] **Step 4: Add `.env.local` to frontend `.gitignore`**

Append to `frontend/.gitignore`:
```
.env.local
```

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "chore(dash-001): scaffold Next.js 15 frontend app"
```

---

### Task 2: Install Dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install runtime dependencies**

```bash
cd frontend
npm install @tanstack/react-query axios lucide-react class-variance-authority clsx tailwind-merge
```

- `@tanstack/react-query`: API state management
- `axios`: HTTP client with interceptors
- `lucide-react`: Icon library
- `class-variance-authority`: Component variant styling (shadcn/ui dependency)
- `clsx` + `tailwind-merge`: Utility for conditional class names (cn helper)

- [ ] **Step 2: Install dev dependencies**

```bash
cd frontend
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event msw
```

- [ ] **Step 3: Verify install**

```bash
cd frontend && npm ls @tanstack/react-query axios lucide-react vitest
```

Expected: All packages listed without errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(dash-001): install runtime and dev dependencies"
```

---

### Task 3: Configure Tailwind Design Tokens

**Files:**
- Modify: `frontend/tailwind.config.ts`
- Create: `frontend/src/app/globals.css`

- [ ] **Step 1: Configure Tailwind with design tokens**

Replace `frontend/tailwind.config.ts` with:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#DC2626",
          light: "#FEF2F2",
        },
        secondary: "#1E293B",
        neutral: {
          50: "#F8FAFC",
          400: "#94A3B8",
          500: "#64748B",
          900: "#0F172A",
        },
        border: "#E2E8F0",
        success: {
          DEFAULT: "#16A34A",
          light: "#F0FDF4",
        },
        info: {
          DEFAULT: "#2563EB",
          light: "#EFF6FF",
        },
        accent: {
          DEFAULT: "#F97316",
          light: "#FFF7ED",
        },
        domain: {
          cybersecurity: "#6366F1",
          "ai-ml": "#059669",
          cloud: "#0EA5E9",
          devops: "#D946EF",
          default: "#64748B",
        },
        steady: {
          DEFAULT: "#64748B",
          light: "#F1F5F9",
        },
      },
      fontFamily: {
        heading: ["var(--font-space-grotesk)", "sans-serif"],
        body: ["var(--font-inter)", "sans-serif"],
      },
      borderRadius: {
        sm: "4px",
        md: "8px",
        lg: "12px",
        pill: "9999px",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(0,0,0,0.05)",
        md: "0 4px 6px -1px rgba(0,0,0,0.07)",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 2: Set up global styles**

Replace `frontend/src/app/globals.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply font-body text-secondary bg-white;
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/tailwind.config.ts frontend/src/app/globals.css
git commit -m "style(dash-001): configure Tailwind design tokens from Pencil design"
```

---

### Task 4: Set Up Fonts and Root Layout

**Files:**
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Configure fonts and root layout**

Replace `frontend/src/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { Space_Grotesk, Inter } from "next/font/google";
import { Providers } from "./providers";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Cognify — Content Intelligence Dashboard",
  description: "Self-driving content platform for trend discovery and article generation",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${inter.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Create Providers component**

Create `frontend/src/app/providers.tsx`:

```tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
```

- [ ] **Step 3: Verify the app still runs**

```bash
cd frontend && npm run dev
```

Expected: App starts without errors on http://localhost:3000.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/app/providers.tsx
git commit -m "feat(dash-001): configure fonts (Space Grotesk + Inter) and TanStack Query provider"
```

---

### Task 5: Set Up shadcn/ui

**Files:**
- Create: `frontend/components.json`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/components/ui/` (multiple files)

- [ ] **Step 1: Initialize shadcn/ui**

```bash
cd frontend
npx shadcn@latest init
```

When prompted:
- Style: Default
- Base color: Slate
- CSS variables: Yes

This creates `components.json` and `src/lib/utils.ts` (with the `cn()` helper).

- [ ] **Step 2: Install shadcn/ui components**

```bash
cd frontend
npx shadcn@latest add button card badge input separator tooltip skeleton
```

- [ ] **Step 3: Verify utils.ts has cn helper**

Check `frontend/src/lib/utils.ts` contains:
```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components.json frontend/src/lib/utils.ts frontend/src/components/ui/
git commit -m "chore(dash-001): initialize shadcn/ui with button, card, badge, skeleton components"
```

---

### Task 6: Set Up Vitest

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Modify: `frontend/tsconfig.json`

- [ ] **Step 1: Create Vitest config**

Create `frontend/vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/app/layout.tsx", "src/app/providers.tsx"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

- [ ] **Step 2: Create Vitest setup file**

Create `frontend/vitest.setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 3: Add test script to package.json**

Add to `frontend/package.json` scripts:
```json
"test": "vitest run",
"test:watch": "vitest",
"test:coverage": "vitest run --coverage"
```

- [ ] **Step 4: Write a smoke test to verify setup**

Create `frontend/src/lib/utils.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { cn } from "./utils";

describe("cn utility", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });

  it("merges conflicting tailwind classes", () => {
    expect(cn("px-4", "px-6")).toBe("px-6");
  });
});
```

- [ ] **Step 5: Run tests to verify setup**

```bash
cd frontend && npm test
```

Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/vitest.config.ts frontend/vitest.setup.ts frontend/src/lib/utils.test.ts frontend/package.json
git commit -m "test(dash-001): configure Vitest with React Testing Library and smoke test"
```

---

## Chunk 2: Types, Mock Data & API Layer

### Task 7: Define TypeScript Types

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/types/domain.ts`

- [ ] **Step 1: Create API types extending backend Pydantic schemas**

Note: `domain` and `trend_status` fields on `RankedTopic` are frontend additions not present in the backend schema. When the real `GET /api/v1/dashboard/topics` endpoint is built, these fields should be added to the backend `RankedTopic` Pydantic model.

Create `frontend/src/types/api.ts`:

```typescript
export interface RawTopic {
  title: string;
  description: string;
  source: string;
  external_url: string;
  trend_score: number;
  discovered_at: string;
  velocity: number;
  domain_keywords: string[];
}

export interface RankedTopic extends RawTopic {
  composite_score: number;
  rank: number;
  source_count: number;
  domain: string;
  trend_status: "trending" | "new" | "rising" | "steady";
}

export interface DashboardMetrics {
  topics_discovered: { value: number; trend: number; direction: "up" | "down" };
  articles_generated: { value: number; trend: number; direction: "up" | "down" };
  avg_research_time: { value: string; trend: number; direction: "up" | "down" };
  published: { value: number; trend: number; direction: "up" | "down" };
}

export interface Article {
  id: string;
  title: string;
  status: "live" | "draft" | "scheduled" | "failed";
  published_at: string;
  views: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: string[];
  };
}
```

- [ ] **Step 2: Create domain types**

Create `frontend/src/types/domain.ts`:

```typescript
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
```

- [ ] **Step 3: Write tests for domain helpers**

Create `frontend/src/types/domain.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { getDomainColor, getDomainLabel } from "./domain";

describe("getDomainColor", () => {
  it("returns correct class for known domains", () => {
    expect(getDomainColor("cybersecurity")).toBe("text-domain-cybersecurity");
    expect(getDomainColor("ai-ml")).toBe("text-domain-ai-ml");
  });

  it("returns default class for unknown domain", () => {
    expect(getDomainColor("unknown")).toBe("text-domain-default");
  });
});

describe("getDomainLabel", () => {
  it("returns display label for known domains", () => {
    expect(getDomainLabel("cybersecurity")).toBe("Cybersecurity");
    expect(getDomainLabel("ai-ml")).toBe("AI / ML");
  });

  it("returns raw domain string for unknown domain", () => {
    expect(getDomainLabel("fintech")).toBe("fintech");
  });
});
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test
```

Expected: All tests pass (cn tests + domain tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/
git commit -m "feat(dash-001): add TypeScript types for API schemas and domain helpers"
```

---

### Task 8: Create Mock Data

**Files:**
- Create: `frontend/src/lib/mock/metrics.ts`
- Create: `frontend/src/lib/mock/articles.ts`
- Create: `frontend/src/lib/mock/topics.ts`

- [ ] **Step 1: Create mock metrics**

Create `frontend/src/lib/mock/metrics.ts`:

```typescript
import type { DashboardMetrics } from "@/types/api";

export const mockMetrics: DashboardMetrics = {
  topics_discovered: { value: 147, trend: 12, direction: "up" },
  articles_generated: { value: 38, trend: 18, direction: "up" },
  avg_research_time: { value: "4.2m", trend: 15, direction: "down" },
  published: { value: 24, trend: 8, direction: "up" },
};
```

- [ ] **Step 2: Create mock articles**

Create `frontend/src/lib/mock/articles.ts`:

```typescript
import type { Article } from "@/types/api";

export const mockArticles: Article[] = [
  {
    id: "art-001",
    title: "The Rise of AI in Threat Detection: A 2026 Overview",
    status: "live",
    published_at: "2026-03-12T10:00:00Z",
    views: 2847,
  },
  {
    id: "art-002",
    title: "Zero Trust Architecture: Implementation Guide for Enterprises",
    status: "live",
    published_at: "2026-03-11T14:30:00Z",
    views: 1543,
  },
  {
    id: "art-003",
    title: "Ransomware Trends 2026: What Security Teams Need to Know",
    status: "live",
    published_at: "2026-03-10T09:15:00Z",
    views: 982,
  },
  {
    id: "art-004",
    title: "NIST Post-Quantum Cryptography Standards: A Practical Overview",
    status: "live",
    published_at: "2026-03-09T16:45:00Z",
    views: 671,
  },
];
```

- [ ] **Step 3: Create mock topics**

Create `frontend/src/lib/mock/topics.ts`:

```typescript
import type { RankedTopic } from "@/types/api";

export const mockTopics: RankedTopic[] = [
  {
    title: "AI-Powered Phishing Detection",
    description: "New machine learning approaches to detecting sophisticated phishing attacks",
    source: "google_trends",
    external_url: "",
    trend_score: 94,
    discovered_at: "2026-03-15T08:00:00Z",
    velocity: 12.5,
    domain_keywords: ["phishing", "ai", "detection"],
    composite_score: 94,
    rank: 1,
    source_count: 3,
    domain: "cybersecurity",
    trend_status: "trending",
  },
  {
    title: "Zero Trust Architecture Trends",
    description: "Latest developments in zero trust network security frameworks",
    source: "arxiv",
    external_url: "",
    trend_score: 88,
    discovered_at: "2026-03-15T07:30:00Z",
    velocity: 8.2,
    domain_keywords: ["zero trust", "architecture"],
    composite_score: 88,
    rank: 2,
    source_count: 2,
    domain: "cybersecurity",
    trend_status: "new",
  },
  {
    title: "Ransomware-as-a-Service Evolution",
    description: "How RaaS platforms are evolving and what it means for defense",
    source: "reddit",
    external_url: "",
    trend_score: 82,
    discovered_at: "2026-03-15T06:45:00Z",
    velocity: 15.1,
    domain_keywords: ["ransomware", "raas"],
    composite_score: 82,
    rank: 3,
    source_count: 2,
    domain: "cybersecurity",
    trend_status: "rising",
  },
  {
    title: "NIST Quantum-Safe Standards",
    description: "NIST finalizes post-quantum cryptography standards for federal agencies",
    source: "arxiv",
    external_url: "",
    trend_score: 76,
    discovered_at: "2026-03-15T05:00:00Z",
    velocity: 6.3,
    domain_keywords: ["quantum", "nist", "cryptography"],
    composite_score: 76,
    rank: 4,
    source_count: 2,
    domain: "cybersecurity",
    trend_status: "rising",
  },
  {
    title: "LLM-Powered Code Review Agents",
    description: "How AI agents are transforming automated code review workflows",
    source: "hackernews",
    external_url: "",
    trend_score: 71,
    discovered_at: "2026-03-15T04:15:00Z",
    velocity: 9.8,
    domain_keywords: ["llm", "code review", "agents"],
    composite_score: 71,
    rank: 5,
    source_count: 2,
    domain: "ai-ml",
    trend_status: "steady",
  },
];
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/mock/
git commit -m "feat(dash-001): add mock data for metrics, articles, and topics"
```

---

### Task 9: Create API Client and Auth

**Files:**
- Create: `frontend/src/lib/api/endpoints.ts`
- Create: `frontend/src/lib/api/client.ts`
- Create: `frontend/src/lib/api/auth.ts`

- [ ] **Step 1: Create endpoint constants**

Create `frontend/src/lib/api/endpoints.ts`:

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const ENDPOINTS = {
  auth: {
    login: `${BASE_URL}/auth/login`,
    refresh: `${BASE_URL}/auth/refresh`,
    logout: `${BASE_URL}/auth/logout`,
  },
  health: `${BASE_URL}/health`,
} as const;
```

- [ ] **Step 2: Create API client with interceptors**

Create `frontend/src/lib/api/client.ts`:

```typescript
import axios from "axios";
import { ENDPOINTS } from "./endpoints";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  config.headers["X-Request-ID"] = crypto.randomUUID();
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const { data } = await axios.post(ENDPOINTS.auth.refresh, {}, { withCredentials: true });
        setAccessToken(data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return apiClient(originalRequest);
      } catch {
        setAccessToken(null);
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  }
);
```

- [ ] **Step 3: Create auth functions**

Create `frontend/src/lib/api/auth.ts`:

```typescript
import { apiClient, setAccessToken } from "./client";
import type { LoginRequest, TokenResponse } from "@/types/api";

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/login", credentials);
  setAccessToken(data.access_token);
  return data;
}

export async function logout(): Promise<void> {
  try {
    await apiClient.post("/auth/logout");
  } finally {
    setAccessToken(null);
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api/
git commit -m "feat(dash-001): add API client with auth interceptors and token management"
```

---

### Task 10: Create TanStack Query Hooks

**Files:**
- Create: `frontend/src/hooks/use-metrics.ts`
- Create: `frontend/src/hooks/use-articles.ts`
- Create: `frontend/src/hooks/use-topics.ts`

- [ ] **Step 1: Create useMetrics hook**

Create `frontend/src/hooks/use-metrics.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import type { DashboardMetrics } from "@/types/api";
import { mockMetrics } from "@/lib/mock/metrics";

async function fetchMetrics(): Promise<DashboardMetrics> {
  // TODO: Replace with real API call when endpoint exists
  return mockMetrics;
}

export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: fetchMetrics,
    staleTime: 15 * 60 * 1000, // 15 minutes
  });
}
```

- [ ] **Step 2: Create useArticles hook**

Create `frontend/src/hooks/use-articles.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import type { Article } from "@/types/api";
import { mockArticles } from "@/lib/mock/articles";

async function fetchArticles(): Promise<Article[]> {
  // TODO: Replace with real API call when endpoint exists
  return mockArticles;
}

export function useArticles() {
  return useQuery({
    queryKey: ["articles"],
    queryFn: fetchArticles,
    staleTime: 15 * 60 * 1000,
  });
}
```

- [ ] **Step 3: Create useTopics hook**

Create `frontend/src/hooks/use-topics.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import type { RankedTopic } from "@/types/api";
import { mockTopics } from "@/lib/mock/topics";

async function fetchTopics(): Promise<RankedTopic[]> {
  // TODO: Replace with GET /api/v1/dashboard/topics when endpoint exists
  return mockTopics;
}

export function useTopics() {
  return useQuery({
    queryKey: ["topics"],
    queryFn: fetchTopics,
    staleTime: 15 * 60 * 1000,
    refetchInterval: 15 * 60 * 1000,
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/
git commit -m "feat(dash-001): add TanStack Query hooks for metrics, articles, and topics"
```

---

## Chunk 3: Common Components

### Task 11: Build Badge Components

**Files:**
- Create: `frontend/src/components/common/trend-badge.tsx`
- Create: `frontend/src/components/common/trend-badge.test.tsx`
- Create: `frontend/src/components/common/status-badge.tsx`
- Create: `frontend/src/components/common/status-badge.test.tsx`
- Create: `frontend/src/components/common/domain-badge.tsx`
- Create: `frontend/src/components/common/domain-badge.test.tsx`

- [ ] **Step 1: Write TrendBadge test**

Create `frontend/src/components/common/trend-badge.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrendBadge } from "./trend-badge";

describe("TrendBadge", () => {
  it("renders trending variant with correct text", () => {
    render(<TrendBadge variant="trending" />);
    expect(screen.getByText("Trending")).toBeInTheDocument();
  });

  it("renders new variant", () => {
    render(<TrendBadge variant="new" />);
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("renders rising variant", () => {
    render(<TrendBadge variant="rising" />);
    expect(screen.getByText("Rising")).toBeInTheDocument();
  });

  it("renders steady variant", () => {
    render(<TrendBadge variant="steady" />);
    expect(screen.getByText("Steady")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/common/trend-badge.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement TrendBadge**

Create `frontend/src/components/common/trend-badge.tsx`:

```tsx
import { cn } from "@/lib/utils";

const VARIANT_STYLES = {
  trending: "bg-primary-light text-primary",
  new: "bg-info-light text-info",
  rising: "bg-accent-light text-accent",
  steady: "bg-steady-light text-steady",
} as const;

const VARIANT_LABELS = {
  trending: "Trending",
  new: "New",
  rising: "Rising",
  steady: "Steady",
} as const;

interface TrendBadgeProps {
  variant: keyof typeof VARIANT_STYLES;
}

export function TrendBadge({ variant }: TrendBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-pill px-2 py-0.5 text-[11px] font-medium",
        VARIANT_STYLES[variant]
      )}
    >
      {VARIANT_LABELS[variant]}
    </span>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/common/trend-badge.test.tsx
```

Expected: 4 tests pass.

- [ ] **Step 5: Write StatusBadge test**

Create `frontend/src/components/common/status-badge.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./status-badge";

describe("StatusBadge", () => {
  it("renders live status", () => {
    render(<StatusBadge status="live" />);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("renders draft status", () => {
    render(<StatusBadge status="draft" />);
    expect(screen.getByText("Draft")).toBeInTheDocument();
  });

  it("renders scheduled status", () => {
    render(<StatusBadge status="scheduled" />);
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("renders failed status", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/common/status-badge.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 7: Implement StatusBadge**

Create `frontend/src/components/common/status-badge.tsx`:

```tsx
import { cn } from "@/lib/utils";

const STATUS_STYLES = {
  live: "bg-success-light text-success",
  draft: "bg-steady-light text-steady",
  scheduled: "bg-accent-light text-accent",
  failed: "bg-primary-light text-primary",
} as const;

const STATUS_LABELS = {
  live: "Live",
  draft: "Draft",
  scheduled: "Scheduled",
  failed: "Failed",
} as const;

interface StatusBadgeProps {
  status: keyof typeof STATUS_STYLES;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-pill px-2 py-0.5 text-[11px] font-medium",
        STATUS_STYLES[status]
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}
```

- [ ] **Step 8: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/common/status-badge.test.tsx
```

Expected: 4 tests pass.

- [ ] **Step 9: Write DomainBadge test**

Create `frontend/src/components/common/domain-badge.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DomainBadge } from "./domain-badge";

describe("DomainBadge", () => {
  it("renders domain label in uppercase", () => {
    render(<DomainBadge domain="cybersecurity" />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
  });

  it("renders AI/ML label correctly", () => {
    render(<DomainBadge domain="ai-ml" />);
    expect(screen.getByText("AI / ML")).toBeInTheDocument();
  });

  it("renders unknown domain as-is", () => {
    render(<DomainBadge domain="fintech" />);
    expect(screen.getByText("fintech")).toBeInTheDocument();
  });
});
```

- [ ] **Step 10: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/common/domain-badge.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 11: Implement DomainBadge**

Create `frontend/src/components/common/domain-badge.tsx`:

```tsx
import { cn } from "@/lib/utils";
import { getDomainColor, getDomainLabel } from "@/types/domain";

interface DomainBadgeProps {
  domain: string;
}

export function DomainBadge({ domain }: DomainBadgeProps) {
  return (
    <span
      className={cn(
        "text-[11px] font-semibold uppercase tracking-wide",
        getDomainColor(domain)
      )}
    >
      {getDomainLabel(domain)}
    </span>
  );
}
```

- [ ] **Step 12: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/common/domain-badge.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 13: Run all tests**

```bash
cd frontend && npm test
```

Expected: All tests pass (cn + domain + TrendBadge + StatusBadge + DomainBadge).

- [ ] **Step 14: Commit**

```bash
git add frontend/src/components/common/
git commit -m "feat(dash-001): add TrendBadge, StatusBadge, and DomainBadge components with tests"
```

---

### Task 12: Build PagePlaceholder Component

**Files:**
- Create: `frontend/src/components/common/page-placeholder.tsx`
- Create: `frontend/src/components/common/page-placeholder.test.tsx`

- [ ] **Step 1: Write test**

Create `frontend/src/components/common/page-placeholder.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PagePlaceholder } from "./page-placeholder";
import { Compass } from "lucide-react";

describe("PagePlaceholder", () => {
  it("renders title and coming soon message", () => {
    render(<PagePlaceholder title="Topic Discovery" icon={Compass} />);
    expect(screen.getByText("Topic Discovery")).toBeInTheDocument();
    expect(screen.getByText("Coming Soon")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/common/page-placeholder.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement PagePlaceholder**

Create `frontend/src/components/common/page-placeholder.tsx`:

```tsx
import type { LucideIcon } from "lucide-react";

interface PagePlaceholderProps {
  title: string;
  icon: LucideIcon;
}

export function PagePlaceholder({ title, icon: Icon }: PagePlaceholderProps) {
  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="text-center">
        <Icon className="mx-auto h-12 w-12 text-neutral-400" />
        <h2 className="mt-4 font-heading text-xl font-semibold text-neutral-900">
          {title}
        </h2>
        <p className="mt-2 text-sm text-neutral-500">Coming Soon</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/common/page-placeholder.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/common/page-placeholder.tsx frontend/src/components/common/page-placeholder.test.tsx
git commit -m "feat(dash-001): add PagePlaceholder component with test"
```

---

## Chunk 4: Layout Components & Routing

### Task 13: Build Sidebar Component

**Files:**
- Create: `frontend/src/components/layout/sidebar.tsx`
- Create: `frontend/src/components/layout/sidebar.test.tsx`

- [ ] **Step 1: Write Sidebar test**

Create `frontend/src/components/layout/sidebar.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "./sidebar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

describe("Sidebar", () => {
  it("renders Cognify logo text", () => {
    render(<Sidebar />);
    expect(screen.getByText("Cognify")).toBeInTheDocument();
  });

  it("renders all navigation items", () => {
    render(<Sidebar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Topics")).toBeInTheDocument();
    expect(screen.getByText("Articles")).toBeInTheDocument();
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Publishing")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders navigation links with correct hrefs", () => {
    render(<Sidebar />);
    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /topics/i })).toHaveAttribute("href", "/topics");
    expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute("href", "/settings");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/layout/sidebar.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement Sidebar**

Create `frontend/src/components/layout/sidebar.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Compass,
  FileText,
  Search,
  Send,
  Settings,
} from "lucide-react";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Topics", href: "/topics", icon: Compass },
  { label: "Articles", href: "/articles", icon: FileText },
  { label: "Research", href: "/research", icon: Search },
  { label: "Publishing", href: "/publishing", icon: Send },
  { label: "Settings", href: "/settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-border bg-neutral-50 px-6 py-8">
      <div className="mb-8">
        <Link href="/" className="font-heading text-xl font-bold text-neutral-900">
          Cognify
        </Link>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary-light text-primary"
                  : "text-neutral-500 hover:bg-neutral-50 hover:text-neutral-900"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/layout/sidebar.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/sidebar.tsx frontend/src/components/layout/sidebar.test.tsx
git commit -m "feat(dash-001): add Sidebar navigation component with tests"
```

---

### Task 14: Build Header Component

**Files:**
- Create: `frontend/src/components/layout/header.tsx`
- Create: `frontend/src/components/layout/header.test.tsx`

- [ ] **Step 1: Write Header test**

Create `frontend/src/components/layout/header.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Header } from "./header";

describe("Header", () => {
  it("renders title and subtitle", () => {
    render(<Header title="Dashboard" subtitle="Monitor your pipeline." />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Monitor your pipeline.")).toBeInTheDocument();
  });

  it("renders action buttons when provided", () => {
    render(
      <Header title="Dashboard" subtitle="Sub">
        <button>New Scan</button>
      </Header>
    );
    expect(screen.getByText("New Scan")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/layout/header.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement Header**

Create `frontend/src/components/layout/header.tsx`:

```tsx
interface HeaderProps {
  title: string;
  subtitle: string;
  children?: React.ReactNode;
}

export function Header({ title, subtitle, children }: HeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="font-heading text-4xl font-semibold tracking-tight text-neutral-900">
          {title}
        </h1>
        <p className="mt-1 text-sm text-neutral-500">{subtitle}</p>
      </div>
      {children && <div className="flex items-center gap-3">{children}</div>}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/layout/header.test.tsx
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/header.tsx frontend/src/components/layout/header.test.tsx
git commit -m "feat(dash-001): add Header component with tests"
```

---

### Task 15: Create Dashboard and Auth Layouts + All Route Pages

**Files:**
- Create: `frontend/src/app/(dashboard)/layout.tsx`
- Create: `frontend/src/app/(dashboard)/page.tsx` (temporary placeholder)
- Create: `frontend/src/app/(dashboard)/topics/page.tsx`
- Create: `frontend/src/app/(dashboard)/articles/page.tsx`
- Create: `frontend/src/app/(dashboard)/research/page.tsx`
- Create: `frontend/src/app/(dashboard)/publishing/page.tsx`
- Create: `frontend/src/app/(dashboard)/settings/page.tsx`
- Create: `frontend/src/app/(auth)/login/page.tsx`

- [ ] **Step 1: Create dashboard layout with sidebar**

Create `frontend/src/app/(dashboard)/layout.tsx`:

```tsx
import { Sidebar } from "@/components/layout/sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto px-12 py-10">{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Create temporary dashboard page**

Create `frontend/src/app/(dashboard)/page.tsx`:

```tsx
export default function DashboardPage() {
  return (
    <div>
      <h1 className="font-heading text-4xl font-semibold text-neutral-900">Dashboard</h1>
      <p className="mt-1 text-sm text-neutral-500">Dashboard content coming in next task.</p>
    </div>
  );
}
```

- [ ] **Step 3: Create placeholder pages**

Create `frontend/src/app/(dashboard)/topics/page.tsx`:

```tsx
import { PagePlaceholder } from "@/components/common/page-placeholder";
import { Compass } from "lucide-react";

export default function TopicsPage() {
  return <PagePlaceholder title="Topic Discovery" icon={Compass} />;
}
```

Create `frontend/src/app/(dashboard)/articles/page.tsx`:

```tsx
import { PagePlaceholder } from "@/components/common/page-placeholder";
import { FileText } from "lucide-react";

export default function ArticlesPage() {
  return <PagePlaceholder title="Articles" icon={FileText} />;
}
```

Create `frontend/src/app/(dashboard)/research/page.tsx`:

```tsx
import { PagePlaceholder } from "@/components/common/page-placeholder";
import { Search } from "lucide-react";

export default function ResearchPage() {
  return <PagePlaceholder title="Research Sessions" icon={Search} />;
}
```

Create `frontend/src/app/(dashboard)/publishing/page.tsx`:

```tsx
import { PagePlaceholder } from "@/components/common/page-placeholder";
import { Send } from "lucide-react";

export default function PublishingPage() {
  return <PagePlaceholder title="Publishing" icon={Send} />;
}
```

Create `frontend/src/app/(dashboard)/settings/page.tsx`:

```tsx
import { PagePlaceholder } from "@/components/common/page-placeholder";
import { Settings } from "lucide-react";

export default function SettingsPage() {
  return <PagePlaceholder title="Settings" icon={Settings} />;
}
```

- [ ] **Step 4: Create login page (basic)**

Create `frontend/src/app/(auth)/login/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { login } from "@/lib/api/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      await login({ email, password });
      router.push("/");
    } catch {
      setError("Invalid credentials. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50">
      <div className="w-full max-w-sm rounded-lg border border-border bg-white p-8 shadow-md">
        <h1 className="mb-2 text-center font-heading text-2xl font-bold text-neutral-900">
          Cognify
        </h1>
        <p className="mb-6 text-center text-sm text-neutral-500">
          Sign in to your account
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p className="text-sm text-primary">{error}</p>}
          <Button type="submit" className="w-full bg-primary hover:bg-primary/90" disabled={isLoading}>
            {isLoading ? "Signing in..." : "Sign In"}
          </Button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify the app runs with sidebar navigation**

```bash
cd frontend && npm run dev
```

Expected: http://localhost:3000 shows sidebar + dashboard content. Clicking nav items navigates to placeholder pages. /login shows login form.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/
git commit -m "feat(dash-001): add dashboard layout, sidebar navigation, placeholder pages, and login"
```

---

## Chunk 5: Dashboard Components

### Task 16: Build MetricCard Component

**Files:**
- Create: `frontend/src/components/dashboard/metric-card.tsx`
- Create: `frontend/src/components/dashboard/metric-card.test.tsx`

- [ ] **Step 1: Write MetricCard test**

Create `frontend/src/components/dashboard/metric-card.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "./metric-card";

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="Topics Discovered" value="147" trend={12} trendDirection="up" />);
    expect(screen.getByText("Topics Discovered")).toBeInTheDocument();
    expect(screen.getByText("147")).toBeInTheDocument();
  });

  it("shows positive trend with up arrow", () => {
    render(<MetricCard label="Published" value="24" trend={8} trendDirection="up" />);
    expect(screen.getByText("+8%")).toBeInTheDocument();
  });

  it("shows negative trend as positive when direction matches positive", () => {
    render(
      <MetricCard label="Avg Research Time" value="4.2m" trend={15} trendDirection="down" positiveDirection="down" />
    );
    expect(screen.getByText("-15%")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/dashboard/metric-card.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement MetricCard**

Create `frontend/src/components/dashboard/metric-card.tsx`:

```tsx
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string;
  trend: number;
  trendDirection: "up" | "down";
  positiveDirection?: "up" | "down";
}

export function MetricCard({
  label,
  value,
  trend,
  trendDirection,
  positiveDirection = "up",
}: MetricCardProps) {
  const isPositive = trendDirection === positiveDirection;
  const TrendIcon = trendDirection === "up" ? TrendingUp : TrendingDown;
  const trendText = `${trendDirection === "up" ? "+" : "-"}${trend}%`;

  return (
    <div className="rounded-md border border-border bg-white p-6 shadow-md">
      <p className="text-sm text-neutral-500">{label}</p>
      <p className="mt-1 font-heading text-4xl font-semibold tracking-tight text-neutral-900">
        {value}
      </p>
      <div className={cn("mt-2 flex items-center gap-1 text-sm", isPositive ? "text-success" : "text-primary")}>
        <TrendIcon className="h-4 w-4" />
        <span>{trendText}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/dashboard/metric-card.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/metric-card.tsx frontend/src/components/dashboard/metric-card.test.tsx
git commit -m "feat(dash-001): add MetricCard component with tests"
```

---

### Task 17: Build TopicRow and TrendingTopicsList

**Files:**
- Create: `frontend/src/components/dashboard/topic-row.tsx`
- Create: `frontend/src/components/dashboard/topic-row.test.tsx`
- Create: `frontend/src/components/dashboard/trending-topics-list.tsx`

- [ ] **Step 1: Write TopicRow test**

Create `frontend/src/components/dashboard/topic-row.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TopicRow } from "./topic-row";
import type { RankedTopic } from "@/types/api";

const mockTopic: RankedTopic = {
  title: "AI-Powered Phishing Detection",
  description: "Test",
  source: "google_trends",
  external_url: "",
  trend_score: 94,
  discovered_at: "2026-03-15T08:00:00Z",
  velocity: 12.5,
  domain_keywords: ["phishing"],
  composite_score: 94,
  rank: 1,
  source_count: 3,
  domain: "cybersecurity",
  trend_status: "trending",
};

describe("TopicRow", () => {
  it("renders topic title", () => {
    render(<TopicRow topic={mockTopic} />);
    expect(screen.getByText("AI-Powered Phishing Detection")).toBeInTheDocument();
  });

  it("renders domain badge", () => {
    render(<TopicRow topic={mockTopic} />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
  });

  it("renders composite score", () => {
    render(<TopicRow topic={mockTopic} />);
    expect(screen.getByText("94")).toBeInTheDocument();
  });

  it("renders trend badge", () => {
    render(<TopicRow topic={mockTopic} />);
    expect(screen.getByText("Trending")).toBeInTheDocument();
  });

  it("renders source label", () => {
    render(<TopicRow topic={mockTopic} />);
    expect(screen.getByText("google_trends")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/dashboard/topic-row.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement TopicRow**

Create `frontend/src/components/dashboard/topic-row.tsx`:

```tsx
import { DomainBadge } from "@/components/common/domain-badge";
import { TrendBadge } from "@/components/common/trend-badge";
import type { RankedTopic } from "@/types/api";

interface TopicRowProps {
  topic: RankedTopic;
}

export function TopicRow({ topic }: TopicRowProps) {
  return (
    <div className="flex items-start justify-between border-b border-border px-5 py-3.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        <DomainBadge domain={topic.domain} />
        <p className="mt-1 font-heading text-sm font-medium text-secondary">
          {topic.title}
        </p>
        <div className="mt-2 flex items-center gap-1.5">
          <TrendBadge variant={topic.trend_status} />
          <span className="text-[11px] text-neutral-400">{topic.source}</span>
        </div>
      </div>
      <span className="ml-4 font-heading text-base font-semibold text-neutral-900">
        {topic.composite_score}
      </span>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/dashboard/topic-row.test.tsx
```

Expected: 5 tests pass.

- [ ] **Step 5: Implement TrendingTopicsList**

Create `frontend/src/components/dashboard/trending-topics-list.tsx`:

```tsx
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { TopicRow } from "./topic-row";
import type { RankedTopic } from "@/types/api";

interface TrendingTopicsListProps {
  topics: RankedTopic[];
  isLoading: boolean;
  isError?: boolean;
  onRetry?: () => void;
}

export function TrendingTopicsList({ topics, isLoading, isError, onRetry }: TrendingTopicsListProps) {
  return (
    <div className="rounded-md border border-border bg-white shadow-md">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="font-heading text-base font-semibold text-neutral-900">Trending Topics</h2>
        <Link href="/topics" className="text-sm font-medium text-primary hover:text-primary/80">
          View All
        </Link>
      </div>
      {isLoading && (
        <div className="space-y-0">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="border-b border-border px-5 py-3.5 last:border-b-0">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="mt-2 h-4 w-3/4" />
              <Skeleton className="mt-2 h-3 w-1/3" />
            </div>
          ))}
        </div>
      )}
      {isError && (
        <div className="px-5 py-10 text-center">
          <p className="text-sm text-neutral-500">Unable to load trending topics</p>
          {onRetry && (
            <button onClick={onRetry} className="mt-2 text-sm font-medium text-primary hover:text-primary/80">
              Retry
            </button>
          )}
        </div>
      )}
      {!isLoading && !isError && topics.length === 0 && (
        <div className="px-5 py-10 text-center">
          <p className="text-sm text-neutral-500">No trending topics found. Try adjusting your domain keywords.</p>
        </div>
      )}
      {!isLoading && !isError && topics.length > 0 && (
        <div>
          {topics.map((topic) => (
            <TopicRow key={`${topic.rank}-${topic.title}`} topic={topic} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Write TrendingTopicsList tests**

Create `frontend/src/components/dashboard/trending-topics-list.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TrendingTopicsList } from "./trending-topics-list";
import { mockTopics } from "@/lib/mock/topics";

describe("TrendingTopicsList", () => {
  it("renders topic rows when data is provided", () => {
    render(<TrendingTopicsList topics={mockTopics} isLoading={false} />);
    expect(screen.getByText("AI-Powered Phishing Detection")).toBeInTheDocument();
    expect(screen.getByText("Trending Topics")).toBeInTheDocument();
    expect(screen.getByText("View All")).toBeInTheDocument();
  });

  it("renders skeleton loading state", () => {
    const { container } = render(<TrendingTopicsList topics={[]} isLoading={true} />);
    const skeletons = container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error state with retry button", async () => {
    const onRetry = vi.fn();
    render(<TrendingTopicsList topics={[]} isLoading={false} isError={true} onRetry={onRetry} />);
    expect(screen.getByText("Unable to load trending topics")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders empty state when no topics", () => {
    render(<TrendingTopicsList topics={[]} isLoading={false} />);
    expect(screen.getByText(/No trending topics found/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Run TrendingTopicsList tests**

```bash
cd frontend && npx vitest run src/components/dashboard/trending-topics-list.test.tsx
```

Expected: 4 tests pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/dashboard/topic-row.tsx frontend/src/components/dashboard/topic-row.test.tsx frontend/src/components/dashboard/trending-topics-list.tsx frontend/src/components/dashboard/trending-topics-list.test.tsx
git commit -m "feat(dash-001): add TopicRow and TrendingTopicsList components with tests"
```

---

### Task 18: Build ArticleRow and RecentArticlesList

**Files:**
- Create: `frontend/src/components/dashboard/article-row.tsx`
- Create: `frontend/src/components/dashboard/article-row.test.tsx`
- Create: `frontend/src/components/dashboard/recent-articles-list.tsx`

- [ ] **Step 1: Write ArticleRow test**

Create `frontend/src/components/dashboard/article-row.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ArticleRow } from "./article-row";
import type { Article } from "@/types/api";

const mockArticle: Article = {
  id: "art-001",
  title: "The Rise of AI in Threat Detection",
  status: "live",
  published_at: "2026-03-12T10:00:00Z",
  views: 2847,
};

describe("ArticleRow", () => {
  it("renders article title", () => {
    render(<ArticleRow article={mockArticle} />);
    expect(screen.getByText("The Rise of AI in Threat Detection")).toBeInTheDocument();
  });

  it("renders status badge", () => {
    render(<ArticleRow article={mockArticle} />);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("renders view count", () => {
    render(<ArticleRow article={mockArticle} />);
    expect(screen.getByText("2,847")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/dashboard/article-row.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement ArticleRow**

Create `frontend/src/components/dashboard/article-row.tsx`:

```tsx
import { Eye } from "lucide-react";
import { StatusBadge } from "@/components/common/status-badge";
import type { Article } from "@/types/api";

interface ArticleRowProps {
  article: Article;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatViews(views: number): string {
  return views.toLocaleString("en-US");
}

export function ArticleRow({ article }: ArticleRowProps) {
  return (
    <div className="flex items-center justify-between border-b border-border px-5 py-4 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="font-heading text-sm font-medium text-secondary">
          {article.title}
        </p>
        <div className="mt-1.5 flex items-center gap-2">
          <StatusBadge status={article.status} />
          <span className="text-[13px] text-neutral-400">{formatDate(article.published_at)}</span>
        </div>
      </div>
      <div className="ml-4 flex items-center gap-1 text-[13px] text-neutral-500">
        <Eye className="h-3.5 w-3.5" />
        <span>{formatViews(article.views)}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/dashboard/article-row.test.tsx
```

Expected: 3 tests pass.

- [ ] **Step 5: Implement RecentArticlesList**

Create `frontend/src/components/dashboard/recent-articles-list.tsx`:

```tsx
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { ArticleRow } from "./article-row";
import type { Article } from "@/types/api";

interface RecentArticlesListProps {
  articles: Article[];
  isLoading: boolean;
  isError?: boolean;
  onRetry?: () => void;
}

export function RecentArticlesList({ articles, isLoading, isError, onRetry }: RecentArticlesListProps) {
  return (
    <div className="rounded-md border border-border bg-white shadow-md">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="font-heading text-base font-semibold text-neutral-900">Recent Articles</h2>
        <Link href="/articles" className="text-sm font-medium text-primary hover:text-primary/80">
          View All
        </Link>
      </div>
      {isLoading && (
        <div className="space-y-0">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="border-b border-border px-5 py-4 last:border-b-0">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="mt-2 h-3 w-1/3" />
            </div>
          ))}
        </div>
      )}
      {isError && (
        <div className="px-5 py-10 text-center">
          <p className="text-sm text-neutral-500">Unable to load recent articles</p>
          {onRetry && (
            <button onClick={onRetry} className="mt-2 text-sm font-medium text-primary hover:text-primary/80">
              Retry
            </button>
          )}
        </div>
      )}
      {!isLoading && !isError && articles.length === 0 && (
        <div className="px-5 py-10 text-center">
          <p className="text-sm text-neutral-500">No articles yet. Generate your first article from a trending topic.</p>
        </div>
      )}
      {!isLoading && !isError && articles.length > 0 && (
        <div>
          {articles.map((article) => (
            <ArticleRow key={article.id} article={article} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Write RecentArticlesList tests**

Create `frontend/src/components/dashboard/recent-articles-list.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecentArticlesList } from "./recent-articles-list";
import { mockArticles } from "@/lib/mock/articles";

describe("RecentArticlesList", () => {
  it("renders article rows when data is provided", () => {
    render(<RecentArticlesList articles={mockArticles} isLoading={false} />);
    expect(screen.getByText("The Rise of AI in Threat Detection: A 2026 Overview")).toBeInTheDocument();
    expect(screen.getByText("Recent Articles")).toBeInTheDocument();
    expect(screen.getByText("View All")).toBeInTheDocument();
  });

  it("renders skeleton loading state", () => {
    const { container } = render(<RecentArticlesList articles={[]} isLoading={true} />);
    const skeletons = container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error state with retry button", async () => {
    const onRetry = vi.fn();
    render(<RecentArticlesList articles={[]} isLoading={false} isError={true} onRetry={onRetry} />);
    expect(screen.getByText("Unable to load recent articles")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders empty state when no articles", () => {
    render(<RecentArticlesList articles={[]} isLoading={false} />);
    expect(screen.getByText(/No articles yet/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Run RecentArticlesList tests**

```bash
cd frontend && npx vitest run src/components/dashboard/recent-articles-list.test.tsx
```

Expected: 4 tests pass.

- [ ] **Step 8: Run all tests**

```bash
cd frontend && npm test
```

Expected: All tests pass.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/dashboard/article-row.tsx frontend/src/components/dashboard/article-row.test.tsx frontend/src/components/dashboard/recent-articles-list.tsx frontend/src/components/dashboard/recent-articles-list.test.tsx
git commit -m "feat(dash-001): add ArticleRow and RecentArticlesList components with tests"
```

---

## Chunk 6: Dashboard Page Assembly & Final Verification

### Task 19: Assemble Dashboard Overview Page

**Files:**
- Modify: `frontend/src/app/(dashboard)/page.tsx`

- [ ] **Step 1: Build the full dashboard page**

Replace `frontend/src/app/(dashboard)/page.tsx` with:

```tsx
"use client";

import { Search, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Header } from "@/components/layout/header";
import { MetricCard } from "@/components/dashboard/metric-card";
import { TrendingTopicsList } from "@/components/dashboard/trending-topics-list";
import { RecentArticlesList } from "@/components/dashboard/recent-articles-list";
import { useMetrics } from "@/hooks/use-metrics";
import { useTopics } from "@/hooks/use-topics";
import { useArticles } from "@/hooks/use-articles";

export default function DashboardPage() {
  const metrics = useMetrics();
  const topics = useTopics();
  const articles = useArticles();

  return (
    <div className="space-y-8">
      <Header
        title="Dashboard"
        subtitle="Monitor trends, track articles, and manage your content pipeline."
      >
        <Button variant="outline" size="sm">
          <Search className="mr-2 h-4 w-4" />
          Search
        </Button>
        <Button size="sm" className="bg-primary hover:bg-primary/90">
          <Zap className="mr-2 h-4 w-4" />
          New Scan
        </Button>
      </Header>

      {metrics.data && (
        <div className="grid grid-cols-4 gap-6">
          <MetricCard
            label="Topics Discovered"
            value={String(metrics.data.topics_discovered.value)}
            trend={metrics.data.topics_discovered.trend}
            trendDirection={metrics.data.topics_discovered.direction}
          />
          <MetricCard
            label="Articles Generated"
            value={String(metrics.data.articles_generated.value)}
            trend={metrics.data.articles_generated.trend}
            trendDirection={metrics.data.articles_generated.direction}
          />
          <MetricCard
            label="Avg Research Time"
            value={metrics.data.avg_research_time.value}
            trend={metrics.data.avg_research_time.trend}
            trendDirection={metrics.data.avg_research_time.direction}
            positiveDirection="down"
          />
          <MetricCard
            label="Published"
            value={String(metrics.data.published.value)}
            trend={metrics.data.published.trend}
            trendDirection={metrics.data.published.direction}
          />
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        <TrendingTopicsList
          topics={topics.data ?? []}
          isLoading={topics.isLoading}
          isError={topics.isError}
          onRetry={() => topics.refetch()}
        />
        <RecentArticlesList
          articles={articles.data ?? []}
          isLoading={articles.isLoading}
          isError={articles.isError}
          onRetry={() => articles.refetch()}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the full dashboard renders**

```bash
cd frontend && npm run dev
```

Expected: http://localhost:3000 shows the complete dashboard with:
- Sidebar navigation (6 items)
- Header with "Dashboard" title, Search + New Scan buttons
- 4 metric cards with values and trend indicators
- Trending Topics list with 5 topics (domain labels, badges, scores)
- Recent Articles list with 4 articles (status badges, dates, view counts)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(dashboard\)/page.tsx
git commit -m "feat(dash-001): assemble full dashboard overview page with metrics, topics, and articles"
```

---

### Task 20: Run Full Test Suite and Final Verification

- [ ] **Step 1: Run all unit tests**

```bash
cd frontend && npm test
```

Expected: All tests pass. Check output for count.

- [ ] **Step 2: Run linting**

```bash
cd frontend && npx next lint
```

Expected: No errors.

- [ ] **Step 3: Run TypeScript type check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 4: Build production bundle**

```bash
cd frontend && npm run build
```

Expected: Build succeeds without errors.

- [ ] **Step 5: Visual verification**

Start dev server and manually verify:
1. Dashboard page: all 4 metric cards, trending topics with domain labels, recent articles
2. Sidebar: all 6 nav items, active state highlights correctly
3. Navigate to /topics, /articles, /research, /publishing, /settings — each shows "Coming Soon" placeholder
4. Navigate to /login — shows login form with Cognify branding

- [ ] **Step 6: Final commit if any fixes were needed**

```bash
git add -A && git commit -m "fix(dash-001): address issues found during final verification"
```

Only run this if fixes were needed. Skip if everything passed.
