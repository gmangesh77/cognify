# Cognify Frontend Design Guidelines

> **Source of truth**: `pencil_designs/cognify.pen` + `docs/superpowers/specs/2026-03-13-design-001-design-system-setup.md`
>
> **Rule**: Every frontend change must follow these guidelines. Do NOT change colors, fonts, or spacing without updating this document and the Pencil design file.

---

## Brand Identity

**Aesthetic**: Refined, clean SaaS (Linear/Vercel-inspired). Warm slate neutrals, single red accent, Space Grotesk + Inter typography, subtle shadows.

---

## Colors

### Primary (Red Accent)

| Token | Hex | CSS Variable | Usage |
|-------|-----|-------------|-------|
| `primary` | `#DC2626` | `--color-primary` | CTA buttons, active nav, logo accent, links, selected states |
| `primary-hover` | `#B91C1C` | — | Button hover states |
| `primary-light` | `#FEF2F2` | `--color-primary-light` | Badge backgrounds, selected tab bg, alert bg |

**IMPORTANT**: The shadcn `--primary` CSS variable in `:root` MUST map to `#DC2626` (oklch 0.5 0.21 27), NOT the default black. All `bg-primary`, `text-primary` classes should produce red.

### Secondary & Accent

| Token | Hex | Usage |
|-------|-----|-------|
| `secondary` | `#1E293B` | Dark headings, sidebar text |
| `accent` | `#F97316` | Trending indicators, special callouts |

### Neutrals (Warm Slate)

| Token | Hex | Usage |
|-------|-----|-------|
| `neutral-50` | `#F8FAFC` | Page background |
| `neutral-100` | `#F1F5F9` | Card hover, table headers |
| `neutral-200` | `#E2E8F0` | Borders, dividers |
| `neutral-300` | `#CBD5E1` | Disabled states |
| `neutral-400` | `#94A3B8` | Placeholder text |
| `neutral-500` | `#64748B` | Secondary text, labels |
| `neutral-600` | `#475569` | Body text |
| `neutral-700` | `#334155` | Strong body text |
| `neutral-800` | `#1E293B` | Headings |
| `neutral-900` | `#0F172A` | Primary text |

### Semantic

| Token | Hex | Usage |
|-------|-----|-------|
| `success` / `success-light` | `#16A34A` / `#F0FDF4` | Live status, positive metrics |
| `warning` / `warning-light` | `#D97706` / `#FFFBEB` | Scheduled, caution |
| `error` / `error-light` | `#DC2626` / `#FEF2F2` | Failed, destructive |
| `info` / `info-light` | `#2563EB` / `#EFF6FF` | Info badges |

### Domain Colors

| Domain | Hex | CSS Variable |
|--------|-----|-------------|
| Cybersecurity | `#6366F1` | `--color-domain-cybersecurity` |
| AI / ML | `#059669` | `--color-domain-ai-ml` |
| Cloud | `#0EA5E9` | `--color-domain-cloud` |
| DevOps | `#D946EF` | `--color-domain-devops` |

---

## Typography

### Fonts

| Role | Font | Tailwind Class |
|------|------|---------------|
| Headings, nav, buttons, metrics | **Space Grotesk** | `font-heading` |
| Body text, descriptions, labels | **Inter** | `font-body` (default) |

### Scale

| Role | Size | Weight | Example Class |
|------|------|--------|--------------|
| Page title | 36px | 600 | `text-3xl font-heading font-semibold` |
| Section heading | 30px | 600 | `text-2xl font-heading font-semibold` |
| Card title | 24px | 600 | `text-xl font-heading font-semibold` |
| Subsection | 20px | 500 | `text-lg font-heading font-medium` |
| Nav / Label | 16px | 500 | `text-base font-heading font-medium` |
| Body default | 14px | 400 | `text-sm` |
| Caption / Badge | 12px | 500 | `text-xs font-medium` |

---

## Spacing (4px Grid)

All spacing uses a 4px base grid:

| Token | Value | Tailwind | Usage |
|-------|-------|----------|-------|
| `space-1` | 4px | `p-1`, `gap-1` | Icon-text tight |
| `space-2` | 8px | `p-2`, `gap-2` | Small gaps |
| `space-3` | 12px | `p-3`, `gap-3` | Nav items |
| `space-4` | 16px | `p-4`, `gap-4` | Form fields |
| `space-5` | 20px | `p-5`, `gap-5` | Card internal |
| `space-6` | 24px | `p-6`, `gap-6` | Card padding |
| `space-8` | 32px | `p-8`, `gap-8` | Section gaps |

---

## Border Radius

| Token | Value | Tailwind | Usage |
|-------|-------|----------|-------|
| `radius-sm` | 4px | `rounded-sm` | Badges, tags |
| `radius-md` | 8px | `rounded-md` | Cards, buttons, inputs |
| `radius-lg` | 12px | `rounded-lg` | Modals, panels |
| `radius-pill` | 9999px | `rounded-full` | Pills, filter chips |

---

## Shadows

| Level | Tailwind | Usage |
|-------|----------|-------|
| `shadow-sm` | `shadow-sm` | Buttons, inputs |
| `shadow-md` | `shadow-md` | Cards, dropdowns |
| `shadow-lg` | `shadow-lg` | Modals, popovers |

---

## Component Patterns

### Buttons
- **Primary**: `bg-primary text-white hover:bg-primary/90 rounded-md`
- **Secondary**: `bg-neutral-100 text-neutral-700 hover:bg-neutral-200 rounded-md`
- **Ghost**: `text-neutral-600 hover:bg-neutral-100 rounded-md`
- **Destructive**: `bg-red-600 text-white hover:bg-red-700 rounded-md`

### Cards
- `rounded-lg border border-neutral-200 bg-white shadow-sm`
- Padding: `p-6`
- Hover: `hover:shadow-md transition-shadow`

### Badges / Status
- **Active**: `bg-primary-light text-primary` (red on light red)
- **Success**: `bg-success-light text-success`
- **Warning**: `bg-warning-light text-warning`
- **Failed**: `bg-error-light text-error`
- Shape: `rounded-full px-2.5 py-0.5 text-xs font-medium`

### Sidebar Navigation
- Active item: `bg-primary-light text-primary font-medium`
- Inactive: `text-neutral-500 hover:text-neutral-700 hover:bg-neutral-100`
- Icons: 20px (`h-5 w-5`), spacing `gap-3` from label

### Filter Tabs (Pills)
- Active: `bg-primary text-white rounded-full`
- Inactive: `bg-neutral-100 text-neutral-600 hover:bg-neutral-200 rounded-full`

### Tables
- Header: `bg-neutral-50 text-xs font-medium text-neutral-500 uppercase`
- Rows: `border-b border-neutral-100`
- Hover: `hover:bg-neutral-50`

---

## Visual Studio (Phase 5 / VISUAL-008)

> **Pencil source**: `pencil_designs/cognify.pen`, screens at `x=3200`. Screen 1 (`lZhq7`) is the anchor; component anatomy across SpecCard / StyleChipRail / UsageBadge / SectionHtmlRefinePanel is derived from it.

### Right-side panel anatomy
- **Container**: `aside` with `rounded-lg border border-neutral-200 bg-white shadow-sm`, `p-6`, `gap-5`, max-width 560px (matches Pencil width).
- **Header**: panel title (`text-xl font-heading font-semibold`), spec/render counter (`text-xs text-neutral-500`), `UsageBadge` and close button on the right.
- **Primary actions row**: equal-width `Plan visuals` (primary red) + `Insert into article` (secondary neutral) buttons.
- **Section labels**: `text-xs font-medium uppercase tracking-wide text-neutral-500` for "Page art direction", "Default visual style", "Render quality", "Spec list".

### SpecCard lifecycle (Pencil Screen 2 `pb0Hz`)
Six visual treatments share one anatomy. Always render: header (state pill + role + style + aspect), media area with `aspectRatio` style, footer actions.
- `idle` — dashed-border placeholder, `Plan visual` CTA
- `planning` / `generating` — `bg-warning-light/50` panel, spinner, status text + checklist or ETA
- `done` — rendered image (`object-cover`), `Regenerate` + `Edit` actions
- `error` — `border-error/40` + `bg-error-light` panel, `Retry with Mid` + `Skip` actions
- `refining` — image with `bg-info/30` overlay, refine input + Apply/Cancel
The `data-state` attribute on the `<article>` exposes the current state for tests + visual regression.

### Catalogue is fetched, never mirrored
- **Single source of truth** is the backend response from `GET /api/v1/visuals/styles`.
- Use `getVisualStylesCached()` from `frontend/src/lib/visuals/visualStyles.ts` — it dedupes inflight calls and serves from memory thereafter.
- **DO NOT** add a TypeScript copy of the catalogue. If you need a style label or short_desc, read it from the cached response.

### Image rendering — URL-first
- `RenderResponse` carries either `image_url` (MinIO) or `image_base64` (LocalDisk dev fallback). Always pass the result through `pickGeneratedImageSrc()` from `frontend/src/lib/visuals/imageSrc.ts` — it handles the mode flip.

### Tokens used by Visual Studio
- Status pills: `bg-success-light text-success` (done), `bg-warning-light text-warning` (planning/generating), `bg-error-light text-error` (error), `bg-info-light text-info` (refining), `bg-neutral-100 text-neutral-600` (idle).
- Quality tier card: selected = `border-primary bg-primary-light text-primary`; unselected = `border-neutral-200 bg-white text-neutral-700 hover:bg-neutral-50`.
- All radii follow existing tokens: `rounded-md` for cards/buttons, `rounded-full` for chips/badges, `rounded-lg` for the panel container.

### Boundary invariants for Visual Studio
- **Read-only catalogue**: never mutate the cached `VisualStylesResponse`.
- **No publishing imports**: components in `frontend/src/components/visuals/` MUST NOT import from `frontend/src/lib/api/publications` or anything publishing-shaped — they live next to the article preview, not the publish flow.
- **Don't redesign on the canvas**: if a flow looks wrong on Pencil, raise it with the user before changing the implementation.

---

## Common Anti-Patterns (DO NOT)

- **DO NOT** use black (`#000`) for text — use `neutral-900` (`#0F172A`)
- **DO NOT** use raw hex colors — use CSS variables or Tailwind classes
- **DO NOT** change `--primary` from `#DC2626` — it's the brand color
- **DO NOT** use `font-sans` for headings — use `font-heading` (Space Grotesk)
- **DO NOT** use inline styles — use Tailwind classes
- **DO NOT** add new colors without updating this document and the Pencil file
- **DO NOT** use spacing values outside the 4px grid
